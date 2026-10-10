from drf_spectacular.utils import extend_schema
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    ClassOffering,
    CurriculumBook,
    CurriculumPlan,
    CurriculumUnit,
    DailyLesson,
    LessonStudentAttention,
    Subject,
    TimetableEntry,
    TimetablePeriod,
)
from .serializers import (
    ClassOfferingSerializer,
    CurriculumBookSerializer,
    CurriculumPlanSerializer,
    CurriculumUnitSerializer,
    DailyLessonSerializer,
    LessonStudentAttentionSerializer,
    SubjectSerializer,
    TimetableEntrySerializer,
    TimetablePeriodSerializer,
)
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Academics"])
class SubjectViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.select_related("academic_class")
    serializer_class = SubjectSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "academic_class__name"]
    ordering_fields = ["name", "academic_class__name"]


@extend_schema(tags=["Academics"])
class ClassOfferingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ClassOffering.objects.select_related("academic_year", "academic_class", "class_teacher", "assistant_teacher")
    serializer_class = ClassOfferingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        return queryset

    @action(detail=True, methods=["get"], url_path="profile")
    def profile(self, request, pk=None):
        from apps.exams.models import InternalExamResult
        from apps.students.models import StudentAttendance, StudentEnrollment

        offering = self.get_object()
        enrollments = StudentEnrollment.objects.filter(madrasa=self.get_madrasa(), academic_year=offering.academic_year, academic_class=offering.academic_class)
        attendance = StudentAttendance.objects.filter(madrasa=self.get_madrasa(), student__in=enrollments.values("student_id"), date__range=(offering.academic_year.starts_on, offering.academic_year.ends_on))
        results = InternalExamResult.objects.filter(madrasa=self.get_madrasa(), student__in=enrollments.values("student_id"), subject__academic_class=offering.academic_class)
        plans = offering.curriculum_plans.prefetch_related("units")
        lessons = offering.daily_lessons.all()
        return Response({
            "offering": ClassOfferingSerializer(offering).data,
            "students": enrollments.count(),
            "subjects": Subject.objects.filter(madrasa=self.get_madrasa(), academic_class=offering.academic_class).count(),
            "attendance": {"marked": attendance.count(), "present": attendance.filter(status=StudentAttendance.Status.PRESENT).count(), "absent": attendance.filter(status=StudentAttendance.Status.ABSENT).count()},
            "results": {"count": results.count(), "average_marks": results.aggregate(value=Avg("marks"))["value"] or 0, "passed": results.filter(result=InternalExamResult.Result.PASS).count()},
            "curriculum": {"plans": plans.count(), "completion": round(sum(CurriculumPlanSerializer(plan).data["completion_percentage"] for plan in plans) / plans.count(), 1) if plans.count() else 0, "delayed_units": sum(CurriculumPlanSerializer(plan).data["delayed_units"] for plan in plans)},
            "lessons": {"total": lessons.count(), "delivered": lessons.filter(delivery_status=DailyLesson.DeliveryStatus.DELIVERED).count()},
            "timetable": TimetableEntrySerializer(offering.timetable_entries.select_related("period", "teaching_assignment__teacher", "teaching_assignment__subject"), many=True).data,
        })


@extend_schema(tags=["Curriculum"])
class CurriculumPlanViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CurriculumPlan.objects.select_related("class_offering__academic_class", "class_offering__academic_year", "subject", "teaching_assignment").prefetch_related("books", "units")
    serializer_class = CurriculumPlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        offering = self.request.query_params.get("class_offering")
        return queryset.filter(class_offering_id=offering) if offering else queryset


@extend_schema(tags=["Curriculum"])
class CurriculumBookViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CurriculumBook.objects.select_related("plan")
    serializer_class = CurriculumBookSerializer


@extend_schema(tags=["Curriculum"])
class CurriculumUnitViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = CurriculumUnit.objects.select_related("plan", "book", "parent")
    serializer_class = CurriculumUnitSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        plan = self.request.query_params.get("plan")
        return queryset.filter(plan_id=plan) if plan else queryset

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        unit = self.get_object()
        unit.verified_by = request.user
        unit.verified_at = timezone.now()
        unit.save(update_fields=["verified_by", "verified_at"])
        return Response(self.get_serializer(unit).data)


@extend_schema(tags=["Timetable"])
class TimetablePeriodViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimetablePeriod.objects.select_related("academic_year")
    serializer_class = TimetablePeriodSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        academic_year = self.request.query_params.get("academic_year")
        return queryset.filter(academic_year_id=academic_year) if academic_year else queryset


@extend_schema(tags=["Timetable"])
class TimetableEntryViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = TimetableEntry.objects.select_related("class_offering__academic_class", "period", "teaching_assignment__teacher", "teaching_assignment__subject")
    serializer_class = TimetableEntrySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        offering = self.request.query_params.get("class_offering")
        return queryset.filter(class_offering_id=offering) if offering else queryset

    def _conflicts(self, period, assignment, room="", exclude=None):
        queryset = TimetableEntry.objects.filter(madrasa=self.get_madrasa(), period=period)
        if exclude:
            queryset = queryset.exclude(pk=exclude)
        conflicts = []
        teacher_matches = queryset.filter(teaching_assignment__teacher=assignment.teacher)
        class_matches = queryset.filter(class_offering__academic_class=assignment.academic_class)
        room_matches = queryset.filter(room=room) if room else queryset.none()
        if teacher_matches.exists(): conflicts.append("teacher_overlap")
        if class_matches.exists(): conflicts.append("class_overlap")
        if room_matches.exists(): conflicts.append("room_overlap")
        return conflicts

    def perform_create(self, serializer):
        period, assignment = serializer.validated_data["period"], serializer.validated_data["teaching_assignment"]
        offering = serializer.validated_data["class_offering"]
        if offering.academic_class_id != assignment.academic_class_id or offering.academic_year_id != assignment.academic_year_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Teaching assignment must match the class offering and academic year.")
        conflicts = self._conflicts(period, assignment, serializer.validated_data.get("room", ""))
        if conflicts:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"conflicts": conflicts})
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        from apps.staff.models import TeachingAssignment

        offering = ClassOffering.objects.filter(madrasa=self.get_madrasa(), pk=request.data.get("class_offering")).first()
        if not offering:
            return Response({"detail": "Invalid class offering."}, status=status.HTTP_400_BAD_REQUEST)
        periods = list(TimetablePeriod.objects.filter(madrasa=self.get_madrasa(), academic_year=offering.academic_year).order_by("weekday", "period_number"))
        assignments = list(TeachingAssignment.objects.filter(madrasa=self.get_madrasa(), academic_year=offering.academic_year, academic_class=offering.academic_class, is_active=True).select_related("teacher", "subject"))
        created, conflicts = [], []
        with transaction.atomic():
            for assignment in assignments:
                needed = assignment.weekly_periods - TimetableEntry.objects.filter(class_offering=offering, teaching_assignment=assignment).count()
                for _ in range(max(needed, 0)):
                    available = next((period for period in periods if not self._conflicts(period, assignment, offering.room)), None)
                    if not available:
                        conflicts.append({"assignment": assignment.id, "subject": assignment.subject.name, "type": "no_available_period"})
                        break
                    created.append(TimetableEntry.objects.create(madrasa=self.get_madrasa(), class_offering=offering, period=available, teaching_assignment=assignment, room=offering.room, created_by=request.user))
        return Response({"created": len(created), "conflicts": conflicts, "entries": self.get_serializer(created, many=True).data})

    @action(detail=False, methods=["get"])
    def conflicts(self, request):
        entries = self.get_queryset()
        conflicts = []
        for entry in entries:
            types = self._conflicts(entry.period, entry.teaching_assignment, entry.room, entry.pk)
            if types:
                conflicts.append({"entry": entry.pk, "types": types})
        return Response(conflicts)


@extend_schema(tags=["Lessons"])
class DailyLessonViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = DailyLesson.objects.select_related("class_offering__academic_class", "teaching_assignment__teacher", "teaching_assignment__subject", "timetable_entry").prefetch_related("curriculum_units", "student_attention")
    serializer_class = DailyLessonSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        offering = self.request.query_params.get("class_offering")
        teacher = self.request.query_params.get("teacher")
        if offering: queryset = queryset.filter(class_offering_id=offering)
        if teacher: queryset = queryset.filter(teaching_assignment__teacher_id=teacher)
        return queryset

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), submitted_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="add-attention")
    def add_attention(self, request, pk=None):
        lesson = self.get_object()
        serializer = LessonStudentAttentionSerializer(data={**request.data, "lesson": lesson.pk})
        serializer.is_valid(raise_exception=True)
        attention = serializer.save(madrasa=self.get_madrasa())
        return Response(LessonStudentAttentionSerializer(attention).data, status=status.HTTP_201_CREATED)
