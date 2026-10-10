from django.utils import timezone
from rest_framework import serializers

from .models import AlumniEngagement, DisciplineAction, DisciplineAppeal, DisciplineCategory, DisciplineIncident, RewardCategory, RewardNomination, TrainingEnrollment, TrainingProgram


class DisciplineCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DisciplineCategory
        fields = ["id", "name", "code", "default_severity", "description", "is_active"]


class DisciplineActionSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = DisciplineAction
        fields = ["id", "incident", "action_type", "description", "starts_on", "ends_on", "status", "assigned_to", "assigned_to_name", "completed_at", "notes"]

    def get_assigned_to_name(self, item):
        return (item.assigned_to.get_full_name() or item.assigned_to.username) if item.assigned_to else ""


class DisciplineAppealSerializer(serializers.ModelSerializer):
    guardian_name = serializers.CharField(source="guardian.full_name", read_only=True)

    class Meta:
        model = DisciplineAppeal
        fields = ["id", "incident", "guardian", "guardian_name", "reason", "status", "decision", "decided_by", "decided_at", "created_at"]
        read_only_fields = ["status", "decision", "decided_by", "decided_at", "created_at"]


class DisciplineIncidentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    actions = DisciplineActionSerializer(many=True, read_only=True)
    appeals = DisciplineAppealSerializer(many=True, read_only=True)

    class Meta:
        model = DisciplineIncident
        fields = ["id", "incident_number", "student", "student_name", "category", "category_name", "incident_date", "location", "severity", "description", "confidential", "status", "reported_by", "assigned_to", "findings", "resolution", "parent_acknowledged_at", "resolved_by", "resolved_at", "created_at", "updated_at", "actions", "appeals"]
        read_only_fields = ["incident_number", "status", "reported_by", "parent_acknowledged_at", "resolved_by", "resolved_at", "created_at", "updated_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status in [DisciplineIncident.Status.RESOLVED, DisciplineIncident.Status.CLOSED]:
            raise serializers.ValidationError("Resolved or closed incidents are locked.")
        return attrs


class TrainingEnrollmentSerializer(serializers.ModelSerializer):
    participant_name = serializers.SerializerMethodField()

    class Meta:
        model = TrainingEnrollment
        fields = ["id", "program", "staff", "student", "alumni", "participant_name", "status", "attendance_percentage", "assessment_score", "certificate_number", "completed_at"]

    def get_participant_name(self, enrollment):
        if enrollment.staff_id:
            return enrollment.staff.full_name
        if enrollment.student_id:
            return enrollment.student.full_name
        return enrollment.alumni.student.full_name if enrollment.alumni_id else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        identities = [bool(attrs.get("staff")), bool(attrs.get("student")), bool(attrs.get("alumni"))]
        if self.instance:
            identities = [bool(attrs.get("staff", self.instance.staff)), bool(attrs.get("student", self.instance.student)), bool(attrs.get("alumni", self.instance.alumni))]
        if sum(identities) != 1:
            raise serializers.ValidationError("Select exactly one participant.")
        return attrs


class TrainingProgramSerializer(serializers.ModelSerializer):
    enrollments = TrainingEnrollmentSerializer(many=True, read_only=True)
    enrolled_count = serializers.IntegerField(source="enrollments.count", read_only=True)

    class Meta:
        model = TrainingProgram
        fields = ["id", "title", "description", "audience", "trainer_name", "starts_at", "ends_at", "venue", "capacity", "certificate_enabled", "passing_score", "status", "created_by", "created_at", "enrolled_count", "enrollments"]
        read_only_fields = ["created_by", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        end = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"ends_at": "Training end must be later than start."})
        return attrs


class RewardCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RewardCategory
        fields = ["id", "name", "code", "recipient_kind", "default_points", "description", "is_active"]


class RewardNominationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = RewardNomination
        fields = ["id", "category", "category_name", "student", "staff", "alumni", "recipient_name", "title", "citation", "points", "status", "nominated_by", "approved_by", "approved_at", "awarded_at", "certificate_number", "rejection_reason", "created_at"]
        read_only_fields = ["status", "nominated_by", "approved_by", "approved_at", "awarded_at", "certificate_number", "rejection_reason", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        recipients = [bool(attrs.get("student")), bool(attrs.get("staff")), bool(attrs.get("alumni"))]
        if self.instance:
            recipients = [bool(attrs.get("student", self.instance.student)), bool(attrs.get("staff", self.instance.staff)), bool(attrs.get("alumni", self.instance.alumni))]
        if sum(recipients) != 1:
            raise serializers.ValidationError("Select exactly one reward recipient.")
        return attrs


class AlumniEngagementSerializer(serializers.ModelSerializer):
    alumni_name = serializers.CharField(source="alumni.student.full_name", read_only=True)

    class Meta:
        model = AlumniEngagement
        fields = ["id", "alumni", "alumni_name", "engagement_type", "title", "date", "details", "amount", "recorded_by", "created_at"]
        read_only_fields = ["recorded_by", "created_at"]
