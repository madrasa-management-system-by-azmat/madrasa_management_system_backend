from datetime import timedelta

from django.db import OperationalError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.rbac import user_has_permission
from apps.users.tenancy import current_madrasa
from .models import Student, StudentAttendance, StudentAttendanceScan
from .attendance_daily import movement_register, student_day

SCAN_COOLDOWN_SECONDS = 10


class ScanInputSerializer(serializers.Serializer):
    student_id = serializers.CharField(max_length=100, trim_whitespace=True)
    request_id = serializers.UUIDField()


class ScanOutputSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name")
    student_id = serializers.CharField(source="student.registration_number")
    guardian_name = serializers.CharField(source="student.guardian_name", default="")
    roll_number = serializers.CharField(source="student.roll_number", default="")
    class_name = serializers.CharField(source="student.current_class.name", default="")
    department_name = serializers.CharField(source="student.current_class.department.name", default="")
    photo = serializers.ImageField(source="student.photo", read_only=True)

    class Meta:
        model = StudentAttendanceScan
        fields = [
            "id", "student_id", "student_name", "guardian_name", "roll_number",
            "class_name", "department_name", "photo", "date", "sequence",
            "direction", "scanned_at", "request_id", "source", "reason"
        ]


@transaction.atomic
def record_scan(tenant, actor, student_id, request_id):
    # A write FIRST avoids SQLite's deferred read-to-write lock upgrade race.
    # This also locks the student row on databases with row-level locking.
    matched = Student.objects.filter(madrasa=tenant, registration_number=student_id).update(status=F("status"))
    if not matched:
        raise NotFound("اس مدرسہ میں اس شناخت کا طالب علم موجود نہیں ہے۔")
    student = Student.objects.select_related("current_class__department").get(madrasa=tenant, registration_number=student_id)
    previous_request = StudentAttendanceScan.objects.filter(madrasa=tenant, request_id=request_id).first()
    if previous_request:
        if previous_request.student_id != student.pk:
            raise ValidationError("یہ درخواست نمبر کسی دوسرے اسکین کے لیے استعمال ہو چکا ہے۔")
        return previous_request, False
    if student.status != Student.Status.ACTIVE:
        raise ValidationError("صرف فعال طالب علم کی حاضری اسکین کی جا سکتی ہے۔")
    now = timezone.now()
    day = timezone.localdate(now)
    latest = StudentAttendanceScan.objects.filter(student=student).order_by("-scanned_at", "-id").first()
    if latest and now - latest.scanned_at < timedelta(seconds=SCAN_COOLDOWN_SECONDS):
        raise ValidationError(f"دوبارہ اسکین سے پہلے {SCAN_COOLDOWN_SECONDS} سیکنڈ انتظار کریں۔")
    count = StudentAttendanceScan.objects.filter(student=student, date=day).count()
    if count >= 4:
        raise ValidationError("آج کے چاروں اسکین مکمل ہو چکے ہیں۔")
    scan = StudentAttendanceScan.objects.create(
        madrasa=tenant, student=student, date=day, sequence=count + 1,
        direction="entry" if count % 2 == 0 else "exit",
        scanned_at=now, request_id=request_id, recorded_by=actor,
    )
    # Movement and daily attendance are distinct: exiting does not erase presence.
    attendance, created = StudentAttendance.objects.get_or_create(
        student=student, date=day, defaults={"madrasa": tenant, "status": "present"},
    )
    if not created and attendance.status not in ("present", "late"):
        attendance.status = "present"
        attendance.save(update_fields=["status"])
    return scan, True


class StudentScannerAPIView(APIView):
    """Authenticated staff-operated keyboard/USB QR scanner endpoint."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = current_madrasa(request)
        if request.user.is_superuser or request.user.profile.role == "guardian":
            raise PermissionDenied("Staff scanner access required.")
        if not user_has_permission(request.user, "attendance.manage"):
            raise PermissionDenied("Attendance management permission required.")

    def get(self, request):
        day = timezone.localdate()
        scans = StudentAttendanceScan.objects.filter(madrasa=self.tenant, date=day).select_related("student__current_class__department")
        daily, count = movement_register(self.tenant, day, day, page=1, page_size=100)
        response = Response({
            "date": day, "timezone": timezone.get_current_timezone_name(),
            "cooldown_seconds": SCAN_COOLDOWN_SECONDS, "daily_limit": 4,
            "total_scans": scans.count(), "results": ScanOutputSerializer(scans[:100], many=True, context={"request": request}).data,
            "daily": daily, "student_days": count,
        })
        response["Cache-Control"] = "no-store"
        return response

    def post(self, request):
        data = ScanInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            scan, created = record_scan(self.tenant, request.user, **data.validated_data)
        except OperationalError as error:
            if "locked" not in str(error).lower():
                raise
            return Response({"detail": "سسٹم مصروف ہے۔ اسی اسکین کو دوبارہ بھیجیں۔"}, status=503)
        response = Response({"scan": ScanOutputSerializer(scan, context={"request": request}).data, "replayed": not created,
                     "daily": student_day(self.tenant, scan.student, scan.date)}, status=201 if created else 200)
        response["Cache-Control"] = "no-store"
        return response
