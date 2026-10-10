from django.db.models import Count, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin
from .models import AlumniEngagement, DisciplineAction, DisciplineAppeal, DisciplineCategory, DisciplineIncident, RewardCategory, RewardNomination, TrainingEnrollment, TrainingProgram
from .serializers import AlumniEngagementSerializer, DisciplineActionSerializer, DisciplineAppealSerializer, DisciplineCategorySerializer, DisciplineIncidentSerializer, RewardCategorySerializer, RewardNominationSerializer, TrainingEnrollmentSerializer, TrainingProgramSerializer


class DevelopmentBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


class DisciplineCategoryViewSet(DevelopmentBaseViewSet):
    queryset = DisciplineCategory.objects.all()
    serializer_class = DisciplineCategorySerializer


class DisciplineIncidentViewSet(DevelopmentBaseViewSet):
    queryset = DisciplineIncident.objects.select_related("student", "category", "assigned_to").prefetch_related("actions", "appeals__guardian")
    serializer_class = DisciplineIncidentSerializer
    search_fields = ["incident_number", "student__full_name", "category__name", "description"]
    ordering_fields = ["incident_date", "severity", "status"]

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), incident_number=DisciplineIncident.issue_number(self.get_madrasa()), reported_by=self.request.user)

    @action(detail=True, methods=["post"])
    def start_investigation(self, request, pk=None):
        incident = self.get_object()
        if incident.status != DisciplineIncident.Status.REPORTED:
            return Response({"detail": "Only reported incidents can enter investigation."}, status=400)
        incident.status = DisciplineIncident.Status.INVESTIGATING
        incident.assigned_to = request.user
        incident.save(update_fields=["status", "assigned_to", "updated_at"])
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can resolve incidents."}, status=403)
        incident = self.get_object()
        if incident.status not in [DisciplineIncident.Status.INVESTIGATING, DisciplineIncident.Status.ACTION_PENDING, DisciplineIncident.Status.APPEALED]:
            return Response({"detail": "Incident is not ready for resolution."}, status=400)
        incident.status = DisciplineIncident.Status.RESOLVED
        incident.findings = request.data.get("findings", incident.findings)
        incident.resolution = request.data.get("resolution", incident.resolution)
        incident.resolved_by = request.user
        incident.resolved_at = timezone.now()
        incident.save(update_fields=["status", "findings", "resolution", "resolved_by", "resolved_at", "updated_at"])
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=["post"])
    def acknowledge_parent(self, request, pk=None):
        incident = self.get_object()
        if request.user.profile.role == "guardian":
            guardian = request.user.guardian_profile
            if not guardian.student_links.filter(student=incident.student, portal_access_enabled=True, revoked_at__isnull=True).exists():
                return Response({"detail": "This incident is not linked to the guardian."}, status=403)
        incident.parent_acknowledged_at = timezone.now()
        incident.save(update_fields=["parent_acknowledged_at", "updated_at"])
        return Response(self.get_serializer(incident).data)


class DisciplineActionViewSet(DevelopmentBaseViewSet):
    queryset = DisciplineAction.objects.select_related("incident", "assigned_to")
    serializer_class = DisciplineActionSerializer


class DisciplineAppealViewSet(DevelopmentBaseViewSet):
    queryset = DisciplineAppeal.objects.select_related("incident", "guardian", "decided_by")
    serializer_class = DisciplineAppealSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "guardian":
            queryset = queryset.filter(guardian=self.request.user.guardian_profile)
        return queryset

    def perform_create(self, serializer):
        guardian = self.request.user.guardian_profile if self.request.user.profile.role == "guardian" else serializer.validated_data.get("guardian")
        if guardian and not guardian.student_links.filter(student=serializer.validated_data["incident"].student, portal_access_enabled=True, revoked_at__isnull=True).exists():
            raise PermissionDenied("The incident does not belong to the guardian's student.")
        incident = serializer.validated_data["incident"]
        serializer.save(madrasa=self.get_madrasa(), guardian=guardian)
        incident.status = DisciplineIncident.Status.APPEALED
        incident.save(update_fields=["status", "updated_at"])

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can decide appeals."}, status=403)
        appeal = self.get_object()
        result = request.data.get("status")
        if result not in ["accepted", "rejected"]:
            return Response({"status": ["Invalid appeal decision."]}, status=400)
        appeal.status = result
        appeal.decision = request.data.get("decision", "")
        appeal.decided_by = request.user
        appeal.decided_at = timezone.now()
        appeal.save(update_fields=["status", "decision", "decided_by", "decided_at"])
        return Response(self.get_serializer(appeal).data)


class TrainingProgramViewSet(DevelopmentBaseViewSet):
    queryset = TrainingProgram.objects.prefetch_related("enrollments__staff", "enrollments__student", "enrollments__alumni__student")
    serializer_class = TrainingProgramSerializer
    search_fields = ["title", "trainer_name", "venue"]
    ordering_fields = ["starts_at", "status", "audience"]

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


class TrainingEnrollmentViewSet(DevelopmentBaseViewSet):
    queryset = TrainingEnrollment.objects.select_related("program", "staff", "student", "alumni__student")
    serializer_class = TrainingEnrollmentSerializer

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        enrollment = self.get_object()
        score = request.data.get("assessment_score", enrollment.assessment_score)
        attendance = request.data.get("attendance_percentage", enrollment.attendance_percentage)
        enrollment.assessment_score = score
        enrollment.attendance_percentage = attendance
        enrollment.status = "completed" if score is not None and float(score) >= float(enrollment.program.passing_score) else "failed"
        enrollment.completed_at = timezone.now()
        if enrollment.status == "completed" and enrollment.program.certificate_enabled:
            enrollment.certificate_number = f"TRN-{enrollment.program_id}-{enrollment.id:06d}"
        enrollment.save(update_fields=["assessment_score", "attendance_percentage", "status", "completed_at", "certificate_number"])
        return Response(self.get_serializer(enrollment).data)


class RewardCategoryViewSet(DevelopmentBaseViewSet):
    queryset = RewardCategory.objects.all()
    serializer_class = RewardCategorySerializer


class RewardNominationViewSet(DevelopmentBaseViewSet):
    queryset = RewardNomination.objects.select_related("category", "student", "staff", "alumni__student")
    serializer_class = RewardNominationSerializer
    search_fields = ["title", "citation", "student__full_name", "staff__full_name", "alumni__student__full_name"]
    ordering_fields = ["created_at", "status", "points"]

    def perform_create(self, serializer):
        category = serializer.validated_data["category"]
        serializer.save(madrasa=self.get_madrasa(), nominated_by=self.request.user, points=serializer.validated_data.get("points") or category.default_points)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can approve rewards."}, status=403)
        nomination = self.get_object()
        nomination.status = RewardNomination.Status.APPROVED
        nomination.approved_by = request.user
        nomination.approved_at = timezone.now()
        nomination.save(update_fields=["status", "approved_by", "approved_at"])
        return Response(self.get_serializer(nomination).data)

    @action(detail=True, methods=["post"])
    def award(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can issue rewards."}, status=403)
        nomination = self.get_object()
        if nomination.status != RewardNomination.Status.APPROVED:
            return Response({"detail": "Approve the nomination first."}, status=400)
        nomination.status = RewardNomination.Status.AWARDED
        nomination.awarded_at = timezone.now()
        nomination.certificate_number = f"RWD-{self.get_madrasa().id}-{timezone.localdate().year}-{nomination.id:06d}"
        nomination.save(update_fields=["status", "awarded_at", "certificate_number"])
        return Response(self.get_serializer(nomination).data)


class AlumniEngagementViewSet(DevelopmentBaseViewSet):
    queryset = AlumniEngagement.objects.select_related("alumni__student", "recorded_by")
    serializer_class = AlumniEngagementSerializer
    search_fields = ["alumni__student__full_name", "title", "details"]
    ordering_fields = ["date", "engagement_type", "amount"]

    def perform_create(self, serializer):
        serializer.save(madrasa=self.get_madrasa(), recorded_by=self.request.user)


class DevelopmentDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = DisciplineIncident.objects.none()

    def list(self, request):
        tenant = self.get_madrasa()
        incidents = DisciplineIncident.objects.filter(madrasa=tenant)
        programs = TrainingProgram.objects.filter(madrasa=tenant)
        rewards = RewardNomination.objects.filter(madrasa=tenant)
        from apps.students.models import AlumniProfile
        alumni = AlumniProfile.objects.filter(madrasa=tenant)
        return Response({"open_incidents": incidents.exclude(status__in=["resolved", "closed"]).count(), "critical_incidents": incidents.filter(severity="critical").exclude(status__in=["resolved", "closed"]).count(), "active_training": programs.filter(status__in=["open", "active"]).count(), "training_enrollments": TrainingEnrollment.objects.filter(madrasa=tenant).count(), "pending_rewards": rewards.filter(status="nominated").count(), "awarded_rewards": rewards.filter(status="awarded").count(), "alumni": alumni.count(), "engagements": AlumniEngagement.objects.filter(madrasa=tenant).count(), "donation_total": AlumniEngagement.objects.filter(madrasa=tenant, engagement_type="donation").aggregate(value=Sum("amount"))["value"] or 0})
