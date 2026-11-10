"""Shared daily projection. Movement events remain append-only and authoritative."""
from collections import defaultdict
from datetime import date, datetime
from uuid import uuid4

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.rbac import user_has_permission
from apps.users.tenancy import current_madrasa
from .models import AcademicClass, Student, StudentAttendance, StudentAttendanceScan

SLOTS = ("entry_1", "exit_1", "entry_2", "exit_2")


def daily_row(student, day, attendance=None, events=()):
    events = sorted(events, key=lambda event: event.sequence)
    times = {slot: None for slot in SLOTS}
    for event in events:
        times[SLOTS[event.sequence - 1]] = event.scanned_at
    seconds = 0
    for start, end in (("entry_1", "exit_1"), ("entry_2", "exit_2")):
        if times[start] and times[end]:
            seconds += max((times[end] - times[start]).total_seconds(), 0)
    return {
        "student": student.pk, "student_name": student.full_name,
        "registration_number": student.registration_number,
        "class_name": student.current_class.name, "date": day,
        "status": attendance.status if attendance else ("present" if events else "unmarked"),
        "remarks": attendance.remarks if attendance else "",
        **times, "event_count": len(events), "complete": len(events) == 4,
        "location": ("inside" if events[-1].direction == "entry" else "outside") if events else "not_recorded",
        "completed_minutes": round(seconds / 60, 1),
        "events": [{"id": event.pk, "sequence": event.sequence, "direction": event.direction,
                    "scanned_at": event.scanned_at, "source": event.source, "reason": event.reason}
                   for event in events],
    }


def student_day(tenant, student, day):
    attendance = StudentAttendance.objects.filter(madrasa=tenant, student=student, date=day).first()
    scans = StudentAttendanceScan.objects.filter(madrasa=tenant, student=student, date=day)
    return daily_row(student, day, attendance, scans)


def movement_register(tenant, start, end, *, class_id=None, student_id=None, roster=False, page=None, page_size=50):
    attendance = StudentAttendance.objects.filter(madrasa=tenant, date__range=(start, end))
    scans = StudentAttendanceScan.objects.filter(madrasa=tenant, date__range=(start, end))
    if class_id:
        attendance = attendance.filter(student__current_class_id=class_id)
        scans = scans.filter(student__current_class_id=class_id)
    if student_id:
        attendance = attendance.filter(student_id=student_id)
        scans = scans.filter(student_id=student_id)
    keys = set(attendance.values_list("student_id", "date")) | set(scans.values_list("student_id", "date"))
    if roster and start == end:
        students = Student.objects.filter(madrasa=tenant, status="active")
        if class_id:
            students = students.filter(current_class_id=class_id)
        if student_id:
            students = students.filter(pk=student_id)
        keys.update((pk, start) for pk in students.values_list("pk", flat=True))
    ordered = sorted(keys, key=lambda pair: (-pair[1].toordinal(), pair[0]))
    count = len(ordered)
    if page is None and count > 10000:
        raise ValidationError("Report exceeds 10,000 student-days. Select a shorter date range.")
    if page is not None:
        ordered = ordered[(page - 1) * page_size:page * page_size]
    ids = {pk for pk, _day in ordered}
    students_by_id = Student.objects.filter(madrasa=tenant, pk__in=ids).select_related("current_class").in_bulk()
    selected = set(ordered)
    attendance_by_key = {(item.student_id, item.date): item for item in attendance.filter(student_id__in=ids)}
    events_by_key = defaultdict(list)
    for event in scans.filter(student_id__in=ids).order_by("student_id", "date", "sequence"):
        key = (event.student_id, event.date)
        if key in selected:
            events_by_key[key].append(event)
    rows = [daily_row(students_by_id[pk], day, attendance_by_key.get((pk, day)), events_by_key[(pk, day)])
            for pk, day in ordered if pk in students_by_id]
    return rows, count


def movement_totals(rows):
    return {
        "events": sum(row["event_count"] for row in rows),
        "completed_days": sum(row["complete"] for row in rows),
        "incomplete_days": sum(0 < row["event_count"] < 4 for row in rows),
        "completed_minutes": round(sum(row["completed_minutes"] for row in rows), 1),
    }


class DailyFilters(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    academic_class = serializers.IntegerField(min_value=1, required=False)
    student = serializers.IntegerField(min_value=1, required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=50)


class AttendanceAccessMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.tenant = current_madrasa(request)
        if request.user.is_superuser or request.user.profile.role == "guardian":
            raise PermissionDenied("Staff attendance access required.")
        codes = ["attendance.manage"] if request.method not in ("GET", "HEAD", "OPTIONS") else ["attendance.view", "attendance.manage"]
        if not any(user_has_permission(request.user, code) for code in codes):
            raise PermissionDenied("Attendance permission required.")


class DailyAttendanceAPIView(AttendanceAccessMixin, APIView):
    def get(self, request):
        form = DailyFilters(data=request.query_params)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        start = data.get("date_from", timezone.localdate())
        end = data.get("date_to", start)
        if start > end or (end - start).days > 366:
            raise ValidationError("Select an ordered date range of at most 367 days.")
        if data.get("academic_class") and not AcademicClass.objects.filter(madrasa=self.tenant, pk=data["academic_class"]).exists():
            raise NotFound("Class not found.")
        if data.get("student") and not Student.objects.filter(madrasa=self.tenant, pk=data["student"]).exists():
            raise NotFound("Student not found.")
        rows, count = movement_register(self.tenant, start, end, class_id=data.get("academic_class"), student_id=data.get("student"), roster=True, page=data["page"], page_size=data["page_size"])
        result = Response({"date_from": start, "date_to": end, "timezone": timezone.get_current_timezone_name(),
                           "count": count, "results": rows,
                           "next_page": data["page"] + 1 if data["page"] * data["page_size"] < count else None,
                           "previous_page": data["page"] - 1 if data["page"] > 1 else None})
        result["Cache-Control"] = "no-store"
        return result


class ManualEventsInput(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    expected_count = serializers.IntegerField(min_value=0, max_value=4)
    times = serializers.ListField(child=serializers.TimeField(), min_length=1, max_length=4)
    reason = serializers.CharField(max_length=500, allow_blank=False)


class AttendanceConflict(APIException):
    status_code = 409
    default_detail = "Attendance changed. Refresh the record before adding times."


@transaction.atomic
def append_manual_events(tenant, actor, data):
    if not Student.objects.filter(madrasa=tenant, pk=data["student"]).update(status=F("status")):
        raise NotFound("Student not found.")
    student = Student.objects.select_related("current_class").get(pk=data["student"], madrasa=tenant)
    day = data["date"]
    existing = list(StudentAttendanceScan.objects.filter(madrasa=tenant, student=student, date=day).order_by("sequence"))
    if len(existing) != data["expected_count"]:
        raise AttendanceConflict()
    if len(existing) + len(data["times"]) > 4:
        raise ValidationError("Only four movement times are allowed per day.")
    now = timezone.now()
    previous = existing[-1].scanned_at if existing else None
    instants = []
    for value in data["times"]:
        instant = timezone.make_aware(datetime.combine(day, value), timezone.get_current_timezone())
        if instant > now or (previous and instant <= previous):
            raise ValidationError("Times must be chronological and must not be in the future.")
        instants.append(instant)
        previous = instant
    for index, instant in enumerate(instants, start=len(existing) + 1):
        StudentAttendanceScan.objects.create(madrasa=tenant, student=student, date=day, sequence=index,
            direction="entry" if index % 2 else "exit", scanned_at=instant, request_id=uuid4(),
            source="manual", reason=data["reason"], recorded_by=actor)
    attendance, _ = StudentAttendance.objects.get_or_create(student=student, date=day, defaults={"madrasa": tenant, "status": "present"})
    if attendance.status not in ("present", "late"):
        attendance.status = "present"
        attendance.save(update_fields=["status"])
    return student_day(tenant, student, day)


class ManualAttendanceEventsAPIView(AttendanceAccessMixin, APIView):
    def post(self, request):
        form = ManualEventsInput(data=request.data)
        form.is_valid(raise_exception=True)
        return Response({"daily": append_manual_events(self.tenant, request.user, form.validated_data)}, status=201)