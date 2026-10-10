from rest_framework import serializers

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


class StaffSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id", "user", "user_username", "full_name", "photo", "cnic", "phone", "role",
            "hire_date", "is_residential", "is_active",
        ]


class StaffAttendanceSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)

    class Meta:
        model = StaffAttendance
        fields = ["id", "staff", "staff_name", "date", "status", "check_in", "check_out", "expected_check_in", "late_minutes", "remarks", "recorded_by"]
        read_only_fields = ["late_minutes", "recorded_by"]


class HalaqaAssignmentSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    halaqa_name = serializers.CharField(source="halaqa.name", read_only=True)

    class Meta:
        model = HalaqaAssignment
        fields = ["id", "staff", "staff_name", "halaqa", "halaqa_name", "assigned_on", "is_active"]
        read_only_fields = ["assigned_on"]


class TeachingAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = TeachingAssignment
        fields = ["id", "teacher", "teacher_name", "academic_year", "academic_year_name", "academic_class", "class_name", "subject", "subject_name", "weekly_periods", "starts_on", "ends_on", "is_active", "assigned_by", "notes", "created_at"]
        read_only_fields = ["assigned_by", "created_at"]


class SyllabusProgressEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SyllabusProgressEntry
        fields = ["id", "plan", "date", "topic", "units_completed", "remarks", "submitted_by", "verified_by", "verified_at", "created_at"]
        read_only_fields = ["submitted_by", "verified_by", "verified_at", "created_at"]


class SyllabusPlanSerializer(serializers.ModelSerializer):
    assignment_label = serializers.SerializerMethodField()
    completed_units = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    progress_entries = SyllabusProgressEntrySerializer(many=True, read_only=True)

    class Meta:
        model = SyllabusPlan
        fields = ["id", "assignment", "assignment_label", "title", "total_units", "completed_units", "completion_percentage", "starts_on", "ends_on", "status", "progress_entries", "created_at"]
        read_only_fields = ["created_at"]

    def get_assignment_label(self, plan):
        return f"{plan.assignment.teacher.full_name} — {plan.assignment.academic_class.name} — {plan.assignment.subject.name}"

    def get_completed_units(self, plan):
        return sum(entry.units_completed for entry in plan.progress_entries.all() if entry.verified_at)

    def get_completion_percentage(self, plan):
        return round(min(self.get_completed_units(plan) / plan.total_units * 100, 100), 1) if plan.total_units else 0


class StaffContributionSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)

    class Meta:
        model = StaffContribution
        fields = ["id", "staff", "staff_name", "category", "title", "scheduled_at", "completed_at", "expected_hours", "actual_hours", "participation_status", "responsibility", "remarks", "assigned_by", "verified_by", "verified_at", "created_at"]
        read_only_fields = ["assigned_by", "verified_by", "verified_at", "created_at"]


class PerformanceMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetric
        fields = ["id", "code", "label", "weight", "raw_value", "normalized_score", "weighted_score", "source_count", "adjustment", "adjustment_reason"]


class PerformanceGoalSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)

    class Meta:
        model = PerformanceGoal
        fields = ["id", "staff", "staff_name", "review", "title", "description", "target_date", "status", "progress_percentage", "teacher_update", "reviewer_remarks", "created_by", "completed_at", "created_at"]
        read_only_fields = ["created_by", "completed_at", "created_at"]

    def validate_progress_percentage(self, value):
        if value > 100:
            raise serializers.ValidationError("Progress cannot exceed 100 percent.")
        return value


class PerformanceReviewSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    metrics = PerformanceMetricSerializer(many=True, read_only=True)
    goals = PerformanceGoalSerializer(many=True, read_only=True)

    class Meta:
        model = PerformanceReview
        fields = ["id", "staff", "staff_name", "review_type", "period_start", "period_end", "status", "overall_score", "rating", "manager_comments", "teacher_comments", "metrics_snapshot", "submitted_at", "reviewed_by", "approved_by", "approved_at", "metrics", "goals", "created_at", "updated_at"]
        read_only_fields = ["overall_score", "rating", "metrics_snapshot", "submitted_at", "reviewed_by", "approved_by", "approved_at", "created_at", "updated_at"]
