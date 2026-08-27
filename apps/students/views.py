from datetime import datetime, time, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import AcademicClass, Department, Halaqa, Student, StudentAttendance
from .serializers import (
    AcademicClassSerializer,
    DepartmentSerializer,
    HalaqaSerializer,
    StudentSerializer,
    StudentOverviewSerializer,
    StudentAttendanceSerializer,
)
from apps.users.permissions import HasTenantRole
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Academics"])
class DepartmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    search_fields = ["name"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["name"]


@extend_schema(tags=["Academics"])
class AcademicClassViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AcademicClass.objects.select_related("department")
    serializer_class = AcademicClassSerializer
    search_fields = ["name", "department__name"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["name", "department__name"]


@extend_schema(tags=["Academics"])
class HalaqaViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Halaqa.objects.all()
    serializer_class = HalaqaSerializer
    search_fields = ["name", "ustad_name"]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["name", "ustad_name"]


@extend_schema(tags=["Students"])
class StudentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Student.objects.select_related("current_class__department", "current_halaqa")
    serializer_class = StudentSerializer
    search_fields = [
        "registration_number",
        "full_name",
        "guardian_name",
        "phone",
        "cnic",
    ]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["full_name", "admission_date", "created_at", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        current_class = self.request.query_params.get("current_class")
        status = self.request.query_params.get("status")

        if current_class:
            queryset = queryset.filter(current_class_id=current_class)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    @extend_schema(responses=StudentOverviewSerializer)
    @action(detail=True, methods=["get"])
    def overview(self, request, pk=None):
        student = self.get_object()
        return Response(StudentOverviewSerializer(student).data)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        """Return live cross-module metrics for the main dashboard."""
        from apps.finance.models import Donation, Expense, StudentFeePayment
        from apps.hifz.models import HifzDailyLog
        from apps.hostel.models import HostelAllocation, HostelRoom

        today = timezone.localdate()
        week_start = today - timedelta(days=6)
        month_start = today.replace(day=1)
        tenant = self.get_madrasa()
        active_students = Student.objects.filter(madrasa=tenant, status=Student.Status.ACTIVE)
        resident_students = active_students.filter(residential_status=Student.ResidentialStatus.RESIDENT)
        hifz_logs = HifzDailyLog.objects.filter(madrasa=tenant, date__range=(week_start, today))
        current_month_payments = StudentFeePayment.objects.filter(madrasa=tenant, payment_date__gte=month_start)
        current_month_donations = Donation.objects.filter(madrasa=tenant, date__gte=month_start)
        current_month_expenses = Expense.objects.filter(madrasa=tenant, date__gte=month_start)
        income = (current_month_payments.aggregate(total=Sum("amount"))["total"] or 0) + (current_month_donations.aggregate(total=Sum("amount"))["total"] or 0)
        expenses = current_month_expenses.aggregate(total=Sum("amount"))["total"] or 0

        activity = []
        for student in Student.objects.filter(madrasa=tenant).order_by("-created_at")[:3]:
            activity.append({"type": "student", "title": "نیا طالب علم داخل کیا گیا", "detail": f"{student.full_name} — {student.class_name if hasattr(student, 'class_name') else student.current_class.name}", "occurred_at": student.created_at})
        for payment in StudentFeePayment.objects.select_related("monthly_fee__student").order_by("-payment_date", "-id")[:3]:
            activity.append({"type": "payment", "title": "فیس وصول ہوئی", "detail": f"{payment.monthly_fee.student.full_name} — {payment.amount} روپے", "occurred_at": timezone.make_aware(datetime.combine(payment.payment_date, time.min))})
        for log in HifzDailyLog.objects.select_related("student").filter(date__gte=week_start).order_by("-date")[:3]:
            activity.append({"type": "hifz", "title": "حفظ ڈائری درج ہوئی", "detail": f"{log.student.full_name} — {log.sabaq_portion or 'سبق درج نہیں'}", "occurred_at": timezone.make_aware(datetime.combine(log.date, time.min))})
        activity.sort(key=lambda item: item["occurred_at"], reverse=True)

        rooms = HostelRoom.objects.filter(madrasa=tenant)
        total_beds = sum(room.capacity for room in rooms)
        occupied_beds = HostelAllocation.objects.filter(madrasa=tenant, is_active=True).count()
        recent_hifz = hifz_logs.select_related("student").order_by("-date", "student__full_name")[:5]
        return Response({
            "generated_on": today,
            "students": {"total": Student.objects.filter(madrasa=tenant).count(), "active": active_students.count(), "resident": resident_students.count()},
            "hostel": {"total_beds": total_beds, "occupied_beds": occupied_beds, "available_beds": max(total_beds - occupied_beds, 0)},
            "hifz": {"weekly_logs": hifz_logs.count(), "students_logged": hifz_logs.values("student_id").distinct().count(), "recent_logs": [{"student_name": log.student.full_name, "portion": log.sabaq_portion or log.sabaqi_portion or log.manzil_portion or "—", "date": log.date} for log in recent_hifz]},
            "finance": {"income": income, "expenses": expenses, "balance": income - expenses, "fees_received": current_month_payments.aggregate(total=Sum("amount"))["total"] or 0, "donations": current_month_donations.aggregate(total=Sum("amount"))["total"] or 0},
            "activity": [{**item, "occurred_at": item["occurred_at"].isoformat()} for item in activity[:6]],
        })


@extend_schema(tags=["Students"])
class StudentAttendanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StudentAttendance.objects.select_related("student__current_class")
    serializer_class = StudentAttendanceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        date = self.request.query_params.get("date")
        academic_class = self.request.query_params.get("academic_class")
        if date:
            queryset = queryset.filter(date=date)
        if academic_class:
            queryset = queryset.filter(student__current_class_id=academic_class)
        return queryset

    @extend_schema(request=dict, responses={200: StudentAttendanceSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="bulk-save")
    def bulk_save(self, request):
        records = request.data.get("records", [])
        if not isinstance(records, list) or not records:
            return Response({"detail": "At least one attendance record is required."}, status=status.HTTP_400_BAD_REQUEST)
        saved = []
        for record in records:
            student_id = record.get("student")
            date = record.get("date")
            status_value = record.get("status", StudentAttendance.Status.PRESENT)
            if not student_id or not date:
                return Response({"detail": "Each record needs student and date."}, status=status.HTTP_400_BAD_REQUEST)
            student = Student.objects.filter(madrasa=self.get_madrasa(), pk=student_id).first()
            if not student:
                return Response({"detail": "Invalid student for this madrasa."}, status=status.HTTP_400_BAD_REQUEST)
            attendance, _ = StudentAttendance.objects.update_or_create(
                madrasa=self.get_madrasa(), student=student,
                date=date,
                defaults={"status": status_value, "remarks": record.get("remarks", "")},
            )
            saved.append(attendance)
        return Response(StudentAttendanceSerializer(saved, many=True).data)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request):
        academic_class = request.query_params.get("academic_class")
        period = request.query_params.get("period", "weekly")
        end_date = request.query_params.get("end_date")
        if not academic_class:
            return Response({"detail": "academic_class is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else timezone.localdate()
        except ValueError:
            return Response({"detail": "end_date must use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        if period == "weekly":
            start = end - timedelta(days=6)
            label = "ہفتہ وار حاضری رپورٹ"
        elif period == "monthly":
            start = end.replace(day=1)
            label = "ماہانہ حاضری رپورٹ"
        elif period == "yearly":
            start = end.replace(month=1, day=1)
            label = "سالانہ حاضری رپورٹ"
        else:
            return Response({"detail": "period must be weekly, monthly, or yearly."}, status=status.HTTP_400_BAD_REQUEST)
        tenant = self.get_madrasa()
        students = Student.objects.filter(madrasa=tenant, current_class_id=academic_class, status=Student.Status.ACTIVE).order_by("full_name")
        records = StudentAttendance.objects.filter(madrasa=tenant, student__in=students, date__range=(start, end)).values("student_id").annotate(
            present=Count("id", filter=Q(status=StudentAttendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=StudentAttendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=StudentAttendance.Status.LEAVE)),
        )
        totals = {item["student_id"]: item for item in records}
        rows = []
        for student in students:
            item = totals.get(student.id, {})
            present, absent, leave = item.get("present", 0), item.get("absent", 0), item.get("leave", 0)
            marked = present + absent + leave
            rows.append({"student": student.id, "student_name": student.full_name, "registration_number": student.registration_number, "present": present, "absent": absent, "leave": leave, "marked_days": marked, "percentage": round((present / marked * 100) if marked else 0, 1)})
        academic_class_object = AcademicClass.objects.get(madrasa=tenant, pk=academic_class)
        return Response({"period": period, "label": label, "date_from": start, "date_to": end, "class_name": academic_class_object.name, "students": rows, "totals": {"present": sum(row["present"] for row in rows), "absent": sum(row["absent"] for row in rows), "leave": sum(row["leave"] for row in rows)}})
