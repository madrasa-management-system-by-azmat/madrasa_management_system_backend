from drf_spectacular.utils import extend_schema
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    HalaqaAssignment,
    PerformanceGoal,
    PerformanceMetric,
    PerformanceReview,
    Staff,
    StaffAttendance,
    StaffContribution,
    SyllabusPlan,
    SyllabusProgressEntry,
    TeachingAssignment,
)
from .serializers import (
    HalaqaAssignmentSerializer,
    PerformanceGoalSerializer,
    PerformanceReviewSerializer,
    StaffAttendanceSerializer,
    StaffContributionSerializer,
    StaffSerializer,
    SyllabusPlanSerializer,
    SyllabusProgressEntrySerializer,
    TeachingAssignmentSerializer,
)
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Staff"])
class StaffViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Staff.objects.select_related("user")
    serializer_class = StaffSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "phone", "cnic", "role"]
    ordering_fields = ["full_name", "hire_date", "role"]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        return queryset.filter(role=role) if role else queryset


@extend_schema(tags=["Staff"])
class StaffAttendanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StaffAttendance.objects.select_related("staff")
    serializer_class = StaffAttendanceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "status"]

    def perform_create(self, serializer):
        expected = serializer.validated_data.get("expected_check_in")
        check_in = serializer.validated_data.get("check_in")
        late_minutes = 0
        if expected and check_in and check_in > expected:
            late_minutes = int((timezone.datetime.combine(timezone.localdate(), check_in) - timezone.datetime.combine(timezone.localdate(), expected)).total_seconds() // 60)
        serializer.save(madrasa=self.get_madrasa(), recorded_by=self.request.user, late_minutes=late_minutes)


@extend_schema(tags=["Staff"])
class HalaqaAssignmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HalaqaAssignment.objects.select_related("staff", "halaqa")
    serializer_class = HalaqaAssignmentSerializer


@extend_schema(tags=["Teacher Performance"])
class TeachingAssignmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TeachingAssignment.objects.select_related("teacher", "academic_year", "academic_class", "subject")
    serializer_class = TeachingAssignmentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["teacher__full_name", "academic_class__name", "subject__name"]
    ordering_fields = ["teacher__full_name", "academic_class__name", "starts_on"]

    def get_queryset(self):
        queryset = super().get_queryset()
        teacher = self.request.query_params.get("teacher")
        academic_year = self.request.query_params.get("academic_year")
        if teacher:
            queryset = queryset.filter(teacher_id=teacher)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset

    def perform_create(self, serializer):
        teacher = serializer.validated_data["teacher"]
        if teacher.role != Staff.Role.TEACHER:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"teacher": "Select a staff member with the teacher role."})
        serializer.save(madrasa=self.get_madrasa(), assigned_by=self.request.user)


@extend_schema(tags=["Teacher Performance"])
class SyllabusPlanViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = SyllabusPlan.objects.select_related("assignment__teacher", "assignment__academic_class", "assignment__subject").prefetch_related("progress_entries")
    serializer_class = SyllabusPlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        teacher = self.request.query_params.get("teacher")
        return queryset.filter(assignment__teacher_id=teacher) if teacher else queryset

    @action(detail=True, methods=["post"], url_path="add-progress")
    def add_progress(self, request, pk=None):
        plan = self.get_object()
        serializer = SyllabusProgressEntrySerializer(data={**request.data, "plan": plan.pk})
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(madrasa=self.get_madrasa(), submitted_by=request.user)
        return Response(SyllabusProgressEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Teacher Performance"])
class SyllabusProgressEntryViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = SyllabusProgressEntry.objects.select_related("plan__assignment__teacher")
    serializer_class = SyllabusProgressEntrySerializer

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        entry = self.get_object()
        entry.verified_by = request.user
        entry.verified_at = timezone.now()
        entry.save(update_fields=["verified_by", "verified_at"])
        return Response(self.get_serializer(entry).data)


@extend_schema(tags=["Teacher Performance"])
class StaffContributionViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StaffContribution.objects.select_related("staff", "assigned_by", "verified_by")
    serializer_class = StaffContributionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        staff = self.request.query_params.get("staff")
        category = self.request.query_params.get("category")
        if staff:
            queryset = queryset.filter(staff_id=staff)
        if category:
            queryset = queryset.filter(category=category)
        return queryset

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), assigned_by=self.request.user)


@extend_schema(tags=["Teacher Performance"])
class PerformanceReviewViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PerformanceReview.objects.select_related("staff", "reviewed_by", "approved_by").prefetch_related("metrics", "goals")
    serializer_class = PerformanceReviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        staff = self.request.query_params.get("staff")
        review_type = self.request.query_params.get("review_type")
        if staff:
            queryset = queryset.filter(staff_id=staff)
        if review_type:
            queryset = queryset.filter(review_type=review_type)
        return queryset

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), reviewed_by=self.request.user)

    def _calculate(self, review):
        attendance = StaffAttendance.objects.filter(madrasa=self.get_madrasa(), staff=review.staff, date__range=(review.period_start, review.period_end))
        marked = attendance.count()
        present_equivalent = attendance.filter(status__in=[StaffAttendance.Status.PRESENT, StaffAttendance.Status.OFFICIAL_DUTY]).count() + attendance.filter(status=StaffAttendance.Status.LATE).count() * 0.8 + attendance.filter(status=StaffAttendance.Status.HALF_DAY).count() * 0.5
        attendance_score = min(present_equivalent / marked * 100, 100) if marked else 0
        total_late = attendance.aggregate(total=Sum("late_minutes"))["total"] or 0
        punctuality_score = max(100 - float(total_late) / max(marked, 1), 0)
        assignments = TeachingAssignment.objects.filter(madrasa=self.get_madrasa(), teacher=review.staff, starts_on__lte=review.period_end).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=review.period_start))
        weekly_periods = assignments.aggregate(total=Sum("weekly_periods"))["total"] or 0
        teaching_load_score = min(float(weekly_periods) / 24 * 100, 100)
        plans = SyllabusPlan.objects.filter(madrasa=self.get_madrasa(), assignment__in=assignments).prefetch_related("progress_entries")
        planned_units = sum(plan.total_units for plan in plans)
        completed_units = sum(entry.units_completed for plan in plans for entry in plan.progress_entries.all() if entry.verified_at and review.period_start <= entry.date <= review.period_end)
        syllabus_score = min(completed_units / planned_units * 100, 100) if planned_units else 0
        contributions = StaffContribution.objects.filter(madrasa=self.get_madrasa(), staff=review.staff, scheduled_at__date__range=(review.period_start, review.period_end))
        assigned_contributions = contributions.count()
        completed_contributions = contributions.filter(participation_status__in=[StaffContribution.ParticipationStatus.ATTENDED, StaffContribution.ParticipationStatus.COMPLETED]).count()
        contribution_score = completed_contributions / assigned_contributions * 100 if assigned_contributions else 0
        metric_data = [
            ("attendance", "حاضری", Decimal("25"), attendance_score, marked),
            ("punctuality", "وقت کی پابندی", Decimal("15"), punctuality_score, marked),
            ("teaching_load", "تدریسی بوجھ", Decimal("20"), teaching_load_score, assignments.count()),
            ("syllabus", "نصاب کی تکمیل", Decimal("25"), syllabus_score, plans.count()),
            ("contribution", "اجلاس، تربیت اور ذمہ داریاں", Decimal("15"), contribution_score, assigned_contributions),
        ]
        with transaction.atomic():
            review.metrics.all().delete()
            total = Decimal("0")
            snapshot = {}
            for code, label, weight, score, source_count in metric_data:
                normalized = Decimal(str(round(score, 2)))
                weighted = normalized * weight / Decimal("100")
                total += weighted
                PerformanceMetric.objects.create(review=review, code=code, label=label, weight=weight, raw_value=normalized, normalized_score=normalized, weighted_score=weighted, source_count=source_count)
                snapshot[code] = {"score": float(normalized), "source_count": source_count}
            review.overall_score = total
            review.rating = "بہترین" if total >= 85 else "بہت اچھا" if total >= 70 else "اچھا" if total >= 55 else "بہتری درکار"
            review.metrics_snapshot = snapshot
            review.save(update_fields=["overall_score", "rating", "metrics_snapshot", "updated_at"])
        return review

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        return Response(self.get_serializer(self._calculate(self.get_object())).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        review = self._calculate(self.get_object())
        review.status = PerformanceReview.Status.SUBMITTED
        review.submitted_at = timezone.now()
        review.teacher_comments = request.data.get("teacher_comments", review.teacher_comments)
        review.save(update_fields=["status", "submitted_at", "teacher_comments", "updated_at"])
        return Response(self.get_serializer(review).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only madrasa administrators can approve performance reviews."}, status=status.HTTP_403_FORBIDDEN)
        review = self._calculate(self.get_object())
        review.status = PerformanceReview.Status.APPROVED
        review.approved_by = request.user
        review.approved_at = timezone.now()
        review.manager_comments = request.data.get("manager_comments", review.manager_comments)
        review.save(update_fields=["status", "approved_by", "approved_at", "manager_comments", "updated_at"])
        return Response(self.get_serializer(review).data)


@extend_schema(tags=["Teacher Performance"])
class PerformanceGoalViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PerformanceGoal.objects.select_related("staff", "review")
    serializer_class = PerformanceGoalSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        staff = self.request.query_params.get("staff")
        return queryset.filter(staff_id=staff) if staff else queryset

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)
