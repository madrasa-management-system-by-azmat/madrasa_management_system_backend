from rest_framework import serializers
from django.utils import timezone

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


class SubjectSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="academic_class.name", read_only=True)

    def validate(self, attrs):
        total_marks = attrs.get("total_marks", self.instance.total_marks if self.instance else 100)
        passing_marks = attrs.get("passing_marks", self.instance.passing_marks if self.instance else 40)
        if passing_marks > total_marks:
            raise serializers.ValidationError({"passing_marks": "Passing marks cannot exceed total marks."})
        return attrs

    class Meta:
        model = Subject
        fields = ["id", "name", "academic_class", "class_name", "total_marks", "passing_marks"]


class ClassOfferingSerializer(serializers.ModelSerializer):
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    class_teacher_name = serializers.CharField(source="class_teacher.full_name", read_only=True)
    assistant_teacher_name = serializers.CharField(source="assistant_teacher.full_name", read_only=True)
    enrolled_students = serializers.SerializerMethodField()

    class Meta:
        model = ClassOffering
        fields = ["id", "academic_year", "academic_year_name", "academic_class", "class_name", "section", "class_teacher", "class_teacher_name", "assistant_teacher", "assistant_teacher_name", "room", "capacity", "status", "enrolled_students", "created_at"]
        read_only_fields = ["created_at"]

    def get_enrolled_students(self, offering):
        return offering.academic_year.enrollments.filter(academic_class=offering.academic_class, status="active").count()


class CurriculumBookSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurriculumBook
        fields = ["id", "plan", "title", "author", "publisher", "edition", "sort_order"]


class CurriculumUnitSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = CurriculumUnit
        fields = ["id", "plan", "book", "book_title", "parent", "title", "sequence", "planned_month", "target_start", "target_end", "estimated_periods", "completion_percentage", "completed_on", "status", "delay_reason", "verified_by", "verified_at"]
        read_only_fields = ["verified_by", "verified_at"]

    def validate_completion_percentage(self, value):
        if value > 100:
            raise serializers.ValidationError("Completion cannot exceed 100 percent.")
        return value


class CurriculumPlanSerializer(serializers.ModelSerializer):
    offering_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    books = CurriculumBookSerializer(many=True, read_only=True)
    units = CurriculumUnitSerializer(many=True, read_only=True)
    completion_percentage = serializers.SerializerMethodField()
    delayed_units = serializers.SerializerMethodField()

    class Meta:
        model = CurriculumPlan
        fields = ["id", "class_offering", "offering_name", "subject", "subject_name", "teaching_assignment", "title", "planned_start", "planned_end", "status", "approved_by", "approved_at", "books", "units", "completion_percentage", "delayed_units", "created_at"]
        read_only_fields = ["approved_by", "approved_at", "created_at"]

    def get_offering_name(self, plan):
        return f"{plan.class_offering.academic_class.name} — {plan.class_offering.academic_year.name}"

    def get_completion_percentage(self, plan):
        units = list(plan.units.all())
        return round(sum(unit.completion_percentage for unit in units) / len(units), 1) if units else 0

    def get_delayed_units(self, plan):
        today = timezone.localdate()
        return sum(1 for unit in plan.units.all() if unit.target_end and unit.target_end < today and unit.completion_percentage < 100)


class TimetablePeriodSerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = TimetablePeriod
        fields = ["id", "academic_year", "weekday", "weekday_label", "period_number", "label", "starts_at", "ends_at"]


class TimetableEntrySerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_offering.academic_class.name", read_only=True)
    weekday = serializers.IntegerField(source="period.weekday", read_only=True)
    weekday_label = serializers.CharField(source="period.get_weekday_display", read_only=True)
    period_number = serializers.IntegerField(source="period.period_number", read_only=True)
    starts_at = serializers.TimeField(source="period.starts_at", read_only=True)
    ends_at = serializers.TimeField(source="period.ends_at", read_only=True)
    teacher_name = serializers.CharField(source="teaching_assignment.teacher.full_name", read_only=True)
    subject_name = serializers.CharField(source="teaching_assignment.subject.name", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = ["id", "class_offering", "class_name", "period", "weekday", "weekday_label", "period_number", "starts_at", "ends_at", "teaching_assignment", "teacher_name", "subject_name", "room", "status", "created_by", "created_at"]
        read_only_fields = ["created_by", "created_at"]


class LessonStudentAttentionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.full_name", read_only=True)

    class Meta:
        model = LessonStudentAttention
        fields = ["id", "lesson", "enrollment", "student_name", "attention_type", "observation", "recommended_action", "follow_up_date", "resolved_at"]


class DailyLessonSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="class_offering.academic_class.name", read_only=True)
    teacher_name = serializers.CharField(source="teaching_assignment.teacher.full_name", read_only=True)
    subject_name = serializers.CharField(source="teaching_assignment.subject.name", read_only=True)
    student_attention = LessonStudentAttentionSerializer(many=True, read_only=True)

    class Meta:
        model = DailyLesson
        fields = ["id", "class_offering", "class_name", "teaching_assignment", "teacher_name", "subject_name", "timetable_entry", "lesson_date", "curriculum_units", "portion_taught", "homework", "lesson_objective", "notes", "delivery_status", "submitted_by", "verified_by", "verified_at", "student_attention", "created_at"]
        read_only_fields = ["submitted_by", "verified_by", "verified_at", "created_at"]
