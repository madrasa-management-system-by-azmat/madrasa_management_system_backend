from datetime import datetime, time, timedelta

from django.db import transaction
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
    AcademicYearSerializer,
    AdmissionApplicationSerializer,
    AdmissionDecisionSerializer,
    AdmissionInterviewSerializer,
    AdmissionTestSerializer,
    AlumniProfileSerializer,
    DepartmentSerializer,
    GraduationRecordSerializer,
    HalaqaSerializer,
    PromotionDecisionSerializer,
    StudentSerializer,
    StudentOverviewSerializer,
    StudentAttendanceSerializer,
    StudentEnrollmentSerializer,
    StudentLifecycleEventSerializer,
    RollNumberChangeSerializer,
    AttendanceAlertSerializer,
    AttendanceAlertRuleSerializer,
)
from .models import (
    AcademicYear,
    AdmissionApplication,
    AdmissionDecision,
    AdmissionInterview,
    AdmissionTest,
    AlumniProfile,
    GraduationRecord,
    PromotionDecision,
    StudentEnrollment,
    StudentLifecycleEvent,
    RollNumberChange,
    AttendanceAlert,
    AttendanceAlertRule,
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

    allowed_transitions = {
        Student.LifecycleStatus.ADMITTED: {Student.LifecycleStatus.ENROLLED, Student.LifecycleStatus.WITHDRAWN},
        Student.LifecycleStatus.ENROLLED: {Student.LifecycleStatus.ON_LEAVE, Student.LifecycleStatus.WITHDRAWN, Student.LifecycleStatus.TRANSFERRED, Student.LifecycleStatus.COMPLETED, Student.LifecycleStatus.EXPELLED, Student.LifecycleStatus.ARCHIVED},
        Student.LifecycleStatus.ON_LEAVE: {Student.LifecycleStatus.ENROLLED, Student.LifecycleStatus.WITHDRAWN},
        Student.LifecycleStatus.COMPLETED: {Student.LifecycleStatus.GRADUATED},
        Student.LifecycleStatus.GRADUATED: {Student.LifecycleStatus.ALUMNI},
        Student.LifecycleStatus.INACTIVE_LEGACY: {Student.LifecycleStatus.ENROLLED, Student.LifecycleStatus.WITHDRAWN, Student.LifecycleStatus.GRADUATED, Student.LifecycleStatus.ARCHIVED},
    }

    def perform_create(self, serializer):
        tenant = self.get_madrasa()
        self._validate_tenant_relations(serializer.validated_data, tenant)
        with transaction.atomic():
            student = serializer.save(madrasa=tenant, created_by=self.request.user, updated_by=self.request.user)
            StudentLifecycleEvent.objects.create(madrasa=tenant, student=student, to_status=student.lifecycle_status, reason="Direct admission", performed_by=self.request.user)
            academic_year = AcademicYear.objects.filter(madrasa=tenant, is_current=True).first()
            if academic_year:
                StudentEnrollment.objects.create(madrasa=tenant, student=student, academic_year=academic_year, academic_class=student.current_class, halaqa=student.current_halaqa, started_on=student.admission_date, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

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

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        student = self.get_object()
        return Response(StudentLifecycleEventSerializer(student.lifecycle_events.all(), many=True).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        student = self.get_object()
        target = request.data.get("to_status")
        if target not in Student.LifecycleStatus.values:
            return Response({"to_status": ["Invalid lifecycle status."]}, status=status.HTTP_400_BAD_REQUEST)
        allowed = self.allowed_transitions.get(student.lifecycle_status, set())
        if target not in allowed:
            return Response({"to_status": [f"Transition from {student.lifecycle_status} to {target} is not allowed."]}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            previous = student.lifecycle_status
            student.lifecycle_status = target
            student.updated_by = request.user
            update_fields = ["lifecycle_status", "updated_by", "updated_at"]
            if target == Student.LifecycleStatus.ON_LEAVE:
                student.status = Student.Status.ON_LEAVE
                update_fields.append("status")
            elif target == Student.LifecycleStatus.ENROLLED:
                student.status = Student.Status.ACTIVE
                update_fields.append("status")
            elif target in {Student.LifecycleStatus.WITHDRAWN, Student.LifecycleStatus.TRANSFERRED, Student.LifecycleStatus.COMPLETED, Student.LifecycleStatus.GRADUATED, Student.LifecycleStatus.ALUMNI, Student.LifecycleStatus.EXPELLED, Student.LifecycleStatus.ARCHIVED}:
                student.status = Student.Status.INACTIVE
                update_fields.append("status")
            if target == Student.LifecycleStatus.GRADUATED:
                student.graduation_date = request.data.get("effective_date") or timezone.localdate()
                update_fields.append("graduation_date")
            if target == Student.LifecycleStatus.ALUMNI:
                student.alumni_since = request.data.get("effective_date") or timezone.localdate()
                update_fields.append("alumni_since")
            if target == Student.LifecycleStatus.ARCHIVED:
                student.archived_at = timezone.now()
                update_fields.append("archived_at")
            student.save(update_fields=update_fields)
            event = StudentLifecycleEvent.objects.create(madrasa=self.get_madrasa(), student=student, from_status=previous, to_status=target, reason=request.data.get("reason", ""), notes=request.data.get("notes", ""), performed_by=request.user)
        return Response(StudentLifecycleEventSerializer(event).data)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "Student records cannot be permanently deleted. Archive the student instead."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @extend_schema(responses={200: dict})
    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        """Return tenant-safe, role-aware metrics for the expanded dashboard."""
        from apps.exams.models import InternalExamPaper
        from apps.finance.models import Donation, Expense, StudentFeePayment, StudentMonthlyFee
        from apps.staff.models import Staff

        today = timezone.localdate()
        month_start = today.replace(day=1)
        tenant = self.get_madrasa()
        all_students = Student.objects.filter(madrasa=tenant)
        active_students = all_students.filter(status=Student.Status.ACTIVE)
        new_students = all_students.filter(admission_date__gte=month_start)

        attendance = StudentAttendance.objects.filter(madrasa=tenant, date=today)
        attendance_counts = {status: 0 for status in StudentAttendance.Status.values}
        for row in attendance.values("status").annotate(total=Count("id")):
            attendance_counts[row["status"]] = row["total"]
        marked = sum(attendance_counts.values())

        role = request.user.profile.role
        can_view_finance = role in ("admin", "accountant")
        finance = None
        if can_view_finance:
            today_payments = StudentFeePayment.objects.filter(madrasa=tenant, payment_date=today)
            month_payments = StudentFeePayment.objects.filter(madrasa=tenant, payment_date__gte=month_start)
            month_donations = Donation.objects.filter(madrasa=tenant, date__gte=month_start)
            month_expenses = Expense.objects.filter(madrasa=tenant, date__gte=month_start)
            invoices = StudentMonthlyFee.objects.filter(madrasa=tenant).prefetch_related("payments", "student")
            outstanding_total = sum(invoice.outstanding_balance for invoice in invoices)
            overdue = [invoice for invoice in invoices if invoice.due_date < today and invoice.outstanding_balance > 0]
            finance = {
                "collected_today": today_payments.aggregate(total=Sum("amount"))["total"] or 0,
                "collected_month": month_payments.aggregate(total=Sum("amount"))["total"] or 0,
                "donations_month": month_donations.aggregate(total=Sum("amount"))["total"] or 0,
                "expenses_month": month_expenses.aggregate(total=Sum("amount"))["total"] or 0,
                "outstanding_total": outstanding_total,
                "overdue_invoices": len(overdue),
                "overdue_students": len({invoice.student_id for invoice in overdue}),
            }

        upcoming_end = today + timedelta(days=14)
        papers = InternalExamPaper.objects.filter(
            madrasa=tenant, paper_date__range=(today, upcoming_end)
        ).select_related("exam", "subject", "subject__academic_class").order_by("paper_date", "paper_time")

        open_attendance_alerts = AttendanceAlert.objects.filter(
            madrasa=tenant,
            status__in=[AttendanceAlert.Status.OPEN, AttendanceAlert.Status.ACKNOWLEDGED],
        ).select_related("student").order_by("-severity", "-count")[:8]

        return Response({
            "generated_on": today,
            "students": {
                "total": all_students.count(),
                "active": active_students.count(),
                "new_this_month": new_students.count(),
                "on_leave": all_students.filter(status=Student.Status.ON_LEAVE).count(),
                "inactive": all_students.filter(status=Student.Status.INACTIVE).count(),
                "graduated": None,
                "withdrawn": None,
            },
            "staff": {
                "teachers_total": Staff.objects.filter(madrasa=tenant, role=Staff.Role.TEACHER).count(),
                "teachers_active": Staff.objects.filter(madrasa=tenant, role=Staff.Role.TEACHER, is_active=True).count(),
            },
            "academics": {"classes_total": AcademicClass.objects.filter(madrasa=tenant).count()},
            "attendance_today": {
                "active_students": active_students.count(),
                "marked": marked,
                "unmarked": max(active_students.count() - marked, 0),
                "present": attendance_counts[StudentAttendance.Status.PRESENT],
                "absent": attendance_counts[StudentAttendance.Status.ABSENT],
                "leave": attendance_counts[StudentAttendance.Status.LEAVE],
                "percentage": round((attendance_counts[StudentAttendance.Status.PRESENT] / marked * 100), 1) if marked else 0,
            },
            "finance": finance,
            "exams": {
                "today": [{"id": paper.id, "exam_name": paper.exam.name, "subject": paper.subject.name, "class_name": paper.subject.academic_class.name, "date": paper.paper_date, "time": paper.paper_time} for paper in papers if paper.paper_date == today],
                "upcoming": [{"id": paper.id, "exam_name": paper.exam.name, "subject": paper.subject.name, "class_name": paper.subject.academic_class.name, "date": paper.paper_date, "time": paper.paper_time} for paper in papers if paper.paper_date > today][:8],
            },
            "early_warnings": {
                "count": AttendanceAlert.objects.filter(madrasa=tenant, status__in=[AttendanceAlert.Status.OPEN, AttendanceAlert.Status.ACKNOWLEDGED]).count(),
                "students": [{"id": alert.student_id, "name": alert.student.full_name, "registration_number": alert.student.registration_number, "reason": alert.reason} for alert in open_attendance_alerts],
            },
            "capabilities": {
                "library": False,
                "tasks": False,
                "meetings": False,
                "decisions": False,
                "announcements": False,
            },
        })


@extend_schema(tags=["Student Lifecycle"])
class AcademicYearViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["starts_on", "ends_on", "name"]

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_current"):
            AcademicYear.objects.filter(madrasa=self.get_madrasa(), is_current=True).update(is_current=False)
        super().perform_create(serializer)

    def perform_update(self, serializer):
        if serializer.validated_data.get("is_current"):
            AcademicYear.objects.filter(madrasa=self.get_madrasa(), is_current=True).exclude(pk=serializer.instance.pk).update(is_current=False)
        super().perform_update(serializer)


@extend_schema(tags=["Student Lifecycle"])
class StudentEnrollmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StudentEnrollment.objects.select_related("student", "academic_year", "academic_class", "halaqa")
    serializer_class = StudentEnrollmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__full_name", "student__guardian_name", "student__registration_number", "roll_number", "academic_class__name"]
    ordering_fields = ["roll_number", "student__full_name", "started_on"]

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        academic_class = self.request.query_params.get("academic_class")
        enrollment_status = self.request.query_params.get("status")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if academic_class:
            queryset = queryset.filter(academic_class_id=academic_class)
        if enrollment_status:
            queryset = queryset.filter(status=enrollment_status)
        return queryset

    def _require_admin(self):
        if self.request.user.profile.role != "admin":
            return Response({"detail": "Only madrasa administrators can change roll numbers."}, status=status.HTTP_403_FORBIDDEN)
        return None

    @action(detail=False, methods=["post"], url_path="generate-roll-numbers")
    def generate_roll_numbers(self, request):
        denied = self._require_admin()
        if denied:
            return denied
        academic_year = request.data.get("academic_year")
        academic_class = request.data.get("academic_class")
        selected_ids = request.data.get("enrollment_ids", [])
        start_number = request.data.get("start_number", 1)
        padding = request.data.get("padding", 3)
        overwrite = bool(request.data.get("overwrite", False))
        try:
            start_number, padding = int(start_number), int(padding)
        except (TypeError, ValueError):
            return Response({"detail": "start_number and padding must be integers."}, status=status.HTTP_400_BAD_REQUEST)
        if start_number < 1 or padding < 1 or padding > 8:
            return Response({"detail": "Use a positive start number and padding from 1 to 8."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = self.get_queryset().filter(academic_year_id=academic_year, academic_class_id=academic_class)
        if selected_ids:
            queryset = queryset.filter(pk__in=selected_ids)
        queryset = queryset.order_by("student__full_name", "student_id")
        if not queryset.exists():
            return Response({"detail": "No matching enrollments were found."}, status=status.HTTP_400_BAD_REQUEST)
        existing_numbers = set(StudentEnrollment.objects.filter(madrasa=self.get_madrasa(), academic_year_id=academic_year, academic_class_id=academic_class).exclude(pk__in=queryset.values("pk")).exclude(roll_number="").values_list("roll_number", flat=True))
        updated = []
        next_number = start_number
        with transaction.atomic():
            for enrollment in queryset.select_for_update():
                if enrollment.roll_number and not overwrite:
                    continue
                roll_number = str(next_number).zfill(padding)
                while roll_number in existing_numbers:
                    next_number += 1
                    roll_number = str(next_number).zfill(padding)
                old_number = enrollment.roll_number
                enrollment.roll_number = roll_number
                enrollment.save(update_fields=["roll_number"])
                RollNumberChange.objects.create(madrasa=self.get_madrasa(), enrollment=enrollment, old_roll_number=old_number, new_roll_number=roll_number, reason="Automatic roll number generation", changed_by=request.user)
                existing_numbers.add(roll_number)
                updated.append(enrollment)
                next_number += 1
        return Response({"updated": len(updated), "enrollments": StudentEnrollmentSerializer(updated, many=True, context={"request": request}).data})

    @action(detail=True, methods=["post"], url_path="change-roll-number")
    def change_roll_number(self, request, pk=None):
        denied = self._require_admin()
        if denied:
            return denied
        enrollment = self.get_object()
        new_number = str(request.data.get("roll_number", "")).strip()
        reason = str(request.data.get("reason", "")).strip()
        if not new_number or not reason:
            return Response({"detail": "A new roll number and reason are required."}, status=status.HTTP_400_BAD_REQUEST)
        conflict = StudentEnrollment.objects.filter(madrasa=self.get_madrasa(), academic_year=enrollment.academic_year, academic_class=enrollment.academic_class, roll_number=new_number).exclude(pk=enrollment.pk).exists()
        if conflict:
            return Response({"roll_number": ["This roll number is already used in the selected class and academic year."]}, status=status.HTTP_400_BAD_REQUEST)
        old_number = enrollment.roll_number
        if old_number == new_number:
            return Response({"detail": "The new roll number is the same as the current number."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            enrollment.roll_number = new_number
            enrollment.save(update_fields=["roll_number"])
            change = RollNumberChange.objects.create(madrasa=self.get_madrasa(), enrollment=enrollment, old_roll_number=old_number, new_roll_number=new_number, reason=reason, changed_by=request.user)
        return Response({"enrollment": StudentEnrollmentSerializer(enrollment, context={"request": request}).data, "change": RollNumberChangeSerializer(change).data})

    @action(detail=True, methods=["get"], url_path="roll-number-history")
    def roll_number_history(self, request, pk=None):
        enrollment = self.get_object()
        return Response(RollNumberChangeSerializer(enrollment.roll_number_changes.select_related("changed_by", "enrollment__student"), many=True).data)


@extend_schema(tags=["Admissions"])
class AdmissionApplicationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AdmissionApplication.objects.select_related("requested_class", "student").prefetch_related("interviews", "tests", "decisions")
    serializer_class = AdmissionApplicationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["application_number", "full_name", "father_name", "guardian_name", "guardian_phone"]
    ordering_fields = ["application_date", "created_at", "full_name", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        application_status = self.request.query_params.get("status")
        return queryset.filter(status=application_status) if application_status else queryset

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), submitted_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        application = self.get_object()
        if application.student_id or application.status == AdmissionApplication.Status.ADMITTED:
            return Response(
                {"detail": "An admitted application cannot be deleted because it is linked to a permanent student record."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        application.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="schedule-interview")
    def schedule_interview(self, request, pk=None):
        application = self.get_object()
        serializer = AdmissionInterviewSerializer(data={**request.data, "application": application.pk})
        serializer.is_valid(raise_exception=True)
        interview = serializer.save(madrasa=self.get_madrasa(), interviewer=request.user)
        application.status = AdmissionApplication.Status.INTERVIEW_SCHEDULED
        application.save(update_fields=["status", "updated_at"])
        return Response(AdmissionInterviewSerializer(interview).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="record-test")
    def record_test(self, request, pk=None):
        application = self.get_object()
        serializer = AdmissionTestSerializer(data={**request.data, "application": application.pk})
        serializer.is_valid(raise_exception=True)
        admission_test = serializer.save(madrasa=self.get_madrasa(), evaluator=request.user)
        application.status = AdmissionApplication.Status.TESTED if admission_test.completed_at else AdmissionApplication.Status.TEST_SCHEDULED
        application.save(update_fields=["status", "updated_at"])
        return Response(AdmissionTestSerializer(admission_test).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        application = self.get_object()
        serializer = AdmissionDecisionSerializer(data={**request.data, "application": application.pk})
        serializer.is_valid(raise_exception=True)
        decision = serializer.save(madrasa=self.get_madrasa(), decided_by=request.user)
        application.status = decision.decision
        application.save(update_fields=["status", "updated_at"])
        return Response(AdmissionDecisionSerializer(decision).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def admit(self, request, pk=None):
        application = self.get_object()
        if application.student_id:
            return Response({"detail": "This application is already linked to a student."}, status=status.HTTP_400_BAD_REQUEST)
        approved = application.decisions.filter(decision=AdmissionDecision.Decision.APPROVED).order_by("-decided_at").first()
        if not approved:
            return Response({"detail": "Approve the application before admission."}, status=status.HTTP_400_BAD_REQUEST)
        academic_year = AcademicYear.objects.filter(madrasa=self.get_madrasa(), is_current=True).first()
        if not academic_year:
            return Response({"detail": "Create a current academic year before admission."}, status=status.HTTP_400_BAD_REQUEST)
        academic_class = approved.approved_class or application.requested_class
        with transaction.atomic():
            student = Student.objects.create(
                madrasa=self.get_madrasa(),
                full_name=application.full_name,
                guardian_name=application.guardian_name or application.father_name,
                guardian_relation=application.guardian_relation,
                guardian_phone=application.guardian_phone,
                phone=application.guardian_phone,
                gender=application.gender,
                date_of_birth=application.date_of_birth,
                current_class=academic_class,
                admission_date=request.data.get("admission_date") or timezone.localdate(),
                application_date=application.application_date,
                current_address=application.address,
                requested_class=academic_class.name,
                modern_education=application.previous_education,
                health_conditions=application.special_education_needs,
                lifecycle_status=Student.LifecycleStatus.ENROLLED,
                status=Student.Status.ACTIVE,
                admitted_at=timezone.now(),
                created_by=request.user,
                updated_by=request.user,
            )
            enrollment = StudentEnrollment.objects.create(
                madrasa=self.get_madrasa(), student=student, academic_year=academic_year,
                academic_class=academic_class, started_on=student.admission_date, created_by=request.user,
            )
            StudentLifecycleEvent.objects.create(
                madrasa=self.get_madrasa(), student=student,
                to_status=Student.LifecycleStatus.ENROLLED,
                reason="Admission application approved", performed_by=request.user,
                metadata={"application_id": application.pk, "enrollment_id": enrollment.pk},
            )
            application.student = student
            application.status = AdmissionApplication.Status.ADMITTED
            application.save(update_fields=["student", "status", "updated_at"])
        return Response(StudentSerializer(student).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Student Lifecycle"])
class PromotionDecisionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PromotionDecision.objects.select_related("student", "from_enrollment", "target_class", "target_academic_year")
    serializer_class = PromotionDecisionSerializer

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), decided_by=self.request.user)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        decision = self.get_object()
        if decision.applied_at:
            return Response({"detail": "This promotion decision has already been applied."}, status=status.HTTP_400_BAD_REQUEST)
        if decision.decision in {PromotionDecision.Decision.PROMOTE, PromotionDecision.Decision.REPEAT} and (not decision.target_class_id or not decision.target_academic_year_id):
            return Response({"detail": "A target class and academic year are required."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            previous = decision.from_enrollment
            previous.status = StudentEnrollment.Status.PROMOTED if decision.decision == PromotionDecision.Decision.PROMOTE else StudentEnrollment.Status.REPEATED
            previous.ended_on = decision.decided_on
            previous.save(update_fields=["status", "ended_on"])
            if decision.decision in {PromotionDecision.Decision.PROMOTE, PromotionDecision.Decision.REPEAT}:
                enrollment = StudentEnrollment.objects.create(
                    madrasa=self.get_madrasa(), student=decision.student,
                    academic_year=decision.target_academic_year, academic_class=decision.target_class,
                    started_on=decision.decided_on, previous_enrollment=previous, created_by=request.user,
                )
                decision.student.current_class = decision.target_class
                decision.student.lifecycle_status = Student.LifecycleStatus.ENROLLED
                decision.student.status = Student.Status.ACTIVE
                decision.student.updated_by = request.user
                decision.student.save(update_fields=["current_class", "lifecycle_status", "status", "updated_by", "updated_at"])
                StudentLifecycleEvent.objects.create(madrasa=self.get_madrasa(), student=decision.student, from_status=Student.LifecycleStatus.ENROLLED, to_status=Student.LifecycleStatus.ENROLLED, reason=decision.get_decision_display(), notes=decision.notes, performed_by=request.user, metadata={"from_enrollment": previous.pk, "to_enrollment": enrollment.pk})
            decision.applied_at = timezone.now()
            decision.save(update_fields=["applied_at"])
        return Response(PromotionDecisionSerializer(decision).data)


@extend_schema(tags=["Student Lifecycle"])
class GraduationRecordViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = GraduationRecord.objects.select_related("student", "enrollment")
    serializer_class = GraduationRecordSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            graduation = serializer.save(madrasa=self.get_madrasa(), approved_by=self.request.user)
            student = graduation.student
            previous = student.lifecycle_status
            student.lifecycle_status = Student.LifecycleStatus.GRADUATED
            student.status = Student.Status.INACTIVE
            student.graduation_date = graduation.completion_date
            student.updated_by = self.request.user
            student.save(update_fields=["lifecycle_status", "status", "graduation_date", "updated_by", "updated_at"])
            StudentLifecycleEvent.objects.create(madrasa=self.get_madrasa(), student=student, from_status=previous, to_status=Student.LifecycleStatus.GRADUATED, reason="Graduation approved", performed_by=self.request.user, metadata={"graduation_record": graduation.pk})


@extend_schema(tags=["Student Lifecycle"])
class AlumniProfileViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = AlumniProfile.objects.select_related("student", "graduation_record")
    serializer_class = AlumniProfileSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            alumni = serializer.save(madrasa=self.get_madrasa())
            student = alumni.student
            previous = student.lifecycle_status
            student.lifecycle_status = Student.LifecycleStatus.ALUMNI
            student.alumni_since = alumni.alumni_since
            student.updated_by = self.request.user
            student.save(update_fields=["lifecycle_status", "alumni_since", "updated_by", "updated_at"])
            StudentLifecycleEvent.objects.create(madrasa=self.get_madrasa(), student=student, from_status=previous, to_status=Student.LifecycleStatus.ALUMNI, reason="Alumni profile created", performed_by=self.request.user, metadata={"alumni_profile": alumni.pk})


@extend_schema(tags=["Students"])
class StudentAttendanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StudentAttendance.objects.select_related("student__current_class")
    serializer_class = StudentAttendanceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "status"]

    def _refresh_alerts(self, student_ids=None, reference_date=None):
        tenant = self.get_madrasa()
        rule, _ = AttendanceAlertRule.objects.get_or_create(madrasa=tenant)
        if not rule.is_active:
            return
        today = reference_date or timezone.localdate()
        month_start = today.replace(day=1)
        students = Student.objects.filter(madrasa=tenant, status=Student.Status.ACTIVE)
        if student_ids:
            students = students.filter(pk__in=student_ids)
        for student in students:
            monthly_records = list(StudentAttendance.objects.filter(madrasa=tenant, student=student, date__range=(month_start, today)).order_by("date"))
            absence_count = sum(record.status == StudentAttendance.Status.ABSENT for record in monthly_records)
            late_count = sum(record.status == StudentAttendance.Status.LATE for record in monthly_records)
            consecutive = 0
            consecutive_dates = []
            for record in reversed(monthly_records):
                if record.status == StudentAttendance.Status.ABSENT:
                    consecutive += 1
                    consecutive_dates.append(record.date.isoformat())
                else:
                    break
            rules = [
                (AttendanceAlert.AlertType.CONSECUTIVE_ABSENCE, f"consecutive:{today.isoformat()}", consecutive, rule.consecutive_absence_threshold, "مسلسل غیر حاضری", consecutive_dates),
                (AttendanceAlert.AlertType.MONTHLY_ABSENCE, f"month:{today:%Y-%m}", absence_count, rule.monthly_absence_threshold, "ماہانہ غیر حاضری", []),
                (AttendanceAlert.AlertType.REPEATED_LATE, f"month:{today:%Y-%m}", late_count, rule.monthly_late_threshold, "ماہانہ تاخیر", []),
            ]
            for alert_type, period_key, count, threshold, label, dates in rules:
                if count < threshold:
                    continue
                severity = AttendanceAlert.Severity.CRITICAL if count >= threshold + 3 else AttendanceAlert.Severity.HIGH if count >= threshold + 1 else AttendanceAlert.Severity.WARNING
                AttendanceAlert.objects.update_or_create(
                    student=student, alert_type=alert_type, period_key=period_key,
                    defaults={"madrasa": tenant, "count": count, "date_from": month_start, "date_to": today, "severity": severity, "reason": f"{label}: {count} دن", "details": {"threshold": threshold, "dates": dates}},
                )

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
        self._refresh_alerts({attendance.student_id for attendance in saved}, saved[0].date if saved else None)
        return Response(StudentAttendanceSerializer(saved, many=True).data)

    @action(detail=False, methods=["get", "put"], url_path="alert-rules")
    def alert_rules(self, request):
        rule, _ = AttendanceAlertRule.objects.get_or_create(madrasa=self.get_madrasa())
        if request.method == "GET":
            return Response(AttendanceAlertRuleSerializer(rule).data)
        if request.user.profile.role != "admin":
            return Response({"detail": "Only madrasa administrators can update attendance alert rules."}, status=status.HTTP_403_FORBIDDEN)
        serializer = AttendanceAlertRuleSerializer(rule, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="refresh-alerts")
    def refresh_alerts(self, request):
        self._refresh_alerts()
        return Response({"detail": "Attendance alerts refreshed."})

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
            start, label = end - timedelta(days=6), "ہفتہ وار حاضری رپورٹ"
        elif period == "monthly":
            start, label = end.replace(day=1), "ماہانہ حاضری رپورٹ"
        elif period == "yearly":
            start, label = end.replace(month=1, day=1), "سالانہ حاضری رپورٹ"
        else:
            return Response({"detail": "period must be weekly, monthly, or yearly."}, status=status.HTTP_400_BAD_REQUEST)
        tenant = self.get_madrasa()
        students = Student.objects.filter(madrasa=tenant, current_class_id=academic_class, status=Student.Status.ACTIVE).order_by("full_name")
        records = StudentAttendance.objects.filter(madrasa=tenant, student__in=students, date__range=(start, end)).values("student_id").annotate(
            present=Count("id", filter=Q(status=StudentAttendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=StudentAttendance.Status.ABSENT)),
            leave=Count("id", filter=Q(status=StudentAttendance.Status.LEAVE)),
            late=Count("id", filter=Q(status=StudentAttendance.Status.LATE)),
            sick=Count("id", filter=Q(status=StudentAttendance.Status.SICK)),
            outside=Count("id", filter=Q(status=StudentAttendance.Status.OUTSIDE)),
        )
        totals = {item["student_id"]: item for item in records}
        rows = []
        for student in students:
            item = totals.get(student.id, {})
            values = {key: item.get(key, 0) for key in ("present", "absent", "leave", "late", "sick", "outside")}
            marked = sum(values.values())
            rows.append({"student": student.id, "student_name": student.full_name, "registration_number": student.registration_number, **values, "marked_days": marked, "percentage": round((values["present"] / marked * 100) if marked else 0, 1)})
        return Response({"period": period, "label": label, "date_from": start, "date_to": end, "class_name": AcademicClass.objects.get(madrasa=tenant, pk=academic_class).name, "students": rows, "totals": {key: sum(row[key] for row in rows) for key in ("present", "absent", "leave", "late", "sick", "outside")}})


@extend_schema(tags=["Attendance Alerts"])
class AttendanceAlertViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AttendanceAlert.objects.select_related("student__current_class", "acknowledged_by", "resolved_by")
    serializer_class = AttendanceAlertSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__full_name", "student__guardian_name", "student__registration_number", "reason"]
    ordering_fields = ["created_at", "severity", "count", "date_to"]

    def get_queryset(self):
        queryset = super().get_queryset()
        alert_status = self.request.query_params.get("status")
        alert_type = self.request.query_params.get("alert_type")
        academic_class = self.request.query_params.get("academic_class")
        if alert_status:
            queryset = queryset.filter(status=alert_status)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if academic_class:
            queryset = queryset.filter(student__current_class_id=academic_class)
        return queryset

    def _update_status(self, request, alert, target):
        notes = str(request.data.get("notes", "")).strip()
        now = timezone.now()
        if target == AttendanceAlert.Status.ACKNOWLEDGED:
            alert.status = target
            alert.acknowledged_by = request.user
            alert.acknowledged_at = now
            fields = ["status", "acknowledged_by", "acknowledged_at", "updated_at"]
        else:
            alert.status = target
            alert.resolved_by = request.user
            alert.resolved_at = now
            alert.resolution_notes = notes
            fields = ["status", "resolved_by", "resolved_at", "resolution_notes", "updated_at"]
        alert.save(update_fields=fields)
        return Response(self.get_serializer(alert).data)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        return self._update_status(request, self.get_object(), AttendanceAlert.Status.ACKNOWLEDGED)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        return self._update_status(request, self.get_object(), AttendanceAlert.Status.RESOLVED)

    @action(detail=True, methods=["post"])
    def dismiss(self, request, pk=None):
        return self._update_status(request, self.get_object(), AttendanceAlert.Status.DISMISSED)

