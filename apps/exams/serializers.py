from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import (
    AnnualResult,
    ExamAttendance,
    ExamDuty,
    ExamResultChange,
    InternalExam,
    InternalExamPaper,
    InternalExamResult,
    WafaqBoardRegistration,
    WafaqResult,
)


class InternalExamPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    academic_class = serializers.IntegerField(source="subject.academic_class_id", read_only=True)
    class_name = serializers.CharField(source="subject.academic_class.name", read_only=True)

    class Meta:
        model = InternalExamPaper
        fields = ["id", "subject", "subject_name", "academic_class", "class_name", "paper_date", "paper_time", "duration_minutes", "total_marks_snapshot", "passing_marks_snapshot", "class_offering", "room", "syllabus_units", "question_paper", "answer_key", "prepared_by", "approved_by", "approved_at"]
        read_only_fields = ["prepared_by", "approved_by", "approved_at"]

    def validate(self, attrs):
        total = attrs.get("total_marks_snapshot")
        passing = attrs.get("passing_marks_snapshot")
        if total is not None and passing is not None and passing > total:
            raise serializers.ValidationError({"passing_marks_snapshot": "Passing marks cannot exceed total marks."})
        tenant = self.context["request"].user.profile.madrasa
        for related in [attrs.get("subject"), attrs.get("class_offering")]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Paper records must belong to the active madrasa.")
        for unit in attrs.get("syllabus_units", []):
            if unit.plan.madrasa_id != tenant.id:
                raise serializers.ValidationError({"syllabus_units": "Syllabus units must belong to the active madrasa."})
        return attrs


class InternalExamSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    classes = serializers.PrimaryKeyRelatedField(many=True, queryset=InternalExam._meta.get_field("classes").related_model.objects.all(), required=False)
    class_names = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    subjects = serializers.PrimaryKeyRelatedField(many=True, queryset=InternalExam._meta.get_field("subjects").related_model.objects.all(), required=False)
    subject_names = serializers.SerializerMethodField()
    papers = InternalExamPaperSerializer(many=True, required=False)

    def get_class_names(self, exam):
        return [academic_class.name for academic_class in exam.classes.all()]

    def get_subject_names(self, exam):
        return [subject.name for subject in exam.subjects.all()]

    def validate(self, attrs):
        if self.instance and self.instance.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            raise serializers.ValidationError("Finalized examinations are locked.")
        requested_status = attrs.get("status")
        if requested_status in [InternalExam.Status.VERIFIED, InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            raise serializers.ValidationError({"status": "Use the examination workflow actions for this status."})
        tenant = self.context["request"].user.profile.madrasa
        academic_year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        academic_class = attrs.get("academic_class", getattr(self.instance, "academic_class", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        classes = attrs.get("classes", [])
        subjects = attrs.get("subjects", [])
        for related in [academic_year, academic_class, subject, *classes, *subjects]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        class_ids = {item.pk for item in classes}
        subject_ids = {item.pk for item in subjects}
        if academic_class:
            class_ids.add(academic_class.pk)
        if subject:
            subject_ids.add(subject.pk)
        for paper in attrs.get("papers", []):
            if subject_ids and paper["subject"].pk not in subject_ids:
                raise serializers.ValidationError({"papers": "Every paper subject must be selected for the examination."})
            if class_ids and paper["subject"].academic_class_id not in class_ids:
                raise serializers.ValidationError({"papers": "Every paper must belong to an examination class."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        papers = validated_data.pop("papers", [])
        exam = super().create(validated_data)
        tenant = self.context["request"].user.profile.madrasa
        for paper in papers:
            syllabus_units = paper.pop("syllabus_units", [])
            total_marks = paper.pop("total_marks_snapshot", None)
            passing_marks = paper.pop("passing_marks_snapshot", None)
            item = InternalExamPaper.objects.create(
                exam=exam,
                madrasa=tenant,
                total_marks_snapshot=total_marks if total_marks is not None else paper["subject"].total_marks,
                passing_marks_snapshot=passing_marks if passing_marks is not None else paper["subject"].passing_marks,
                **paper,
            )
            item.syllabus_units.set(syllabus_units)
        return exam

    @transaction.atomic
    def update(self, instance, validated_data):
        papers = validated_data.pop("papers", None)
        exam = super().update(instance, validated_data)
        if papers is not None:
            tenant = self.context["request"].user.profile.madrasa
            retained_subject_ids = {paper["subject"].pk for paper in papers}
            removed = exam.papers.exclude(subject_id__in=retained_subject_ids)
            protected = removed.filter(Q(results__isnull=False) | Q(duties__isnull=False) | Q(attendance__isnull=False)).distinct()
            if protected.exists():
                raise serializers.ValidationError({"papers": "Papers with results, duties, or attendance cannot be removed."})
            removed.delete()
            for paper in papers:
                syllabus_units = paper.pop("syllabus_units", None)
                subject = paper["subject"]
                total_marks = paper.pop("total_marks_snapshot", None)
                passing_marks = paper.pop("passing_marks_snapshot", None)
                item, _ = InternalExamPaper.objects.update_or_create(
                    exam=exam,
                    subject=subject,
                    defaults={
                        **paper,
                        "madrasa": tenant,
                        "total_marks_snapshot": total_marks if total_marks is not None else subject.total_marks,
                        "passing_marks_snapshot": passing_marks if passing_marks is not None else subject.passing_marks,
                    },
                )
                if syllabus_units is not None:
                    item.syllabus_units.set(syllabus_units)
        return exam

    class Meta:
        model = InternalExam
        fields = ["id", "name", "academic_year", "exam_type", "term", "status", "instructions", "academic_class", "class_name", "classes", "class_names", "subject", "subject_name", "subjects", "subject_names", "papers", "exam_date", "finalized_by", "finalized_at", "published_at"]
        read_only_fields = ["finalized_by", "finalized_at", "published_at"]


class InternalExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    exam_date = serializers.DateField(source="exam.exam_date", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    total_marks = serializers.SerializerMethodField()
    passing_marks = serializers.SerializerMethodField()

    def get_total_marks(self, result):
        if result.paper and result.paper.total_marks_snapshot is not None:
            return result.paper.total_marks_snapshot
        return result.subject.total_marks if result.subject else 0

    def get_passing_marks(self, result):
        if result.paper and result.paper.passing_marks_snapshot is not None:
            return result.paper.passing_marks_snapshot
        return result.subject.passing_marks if result.subject else 0

    def validate(self, attrs):
        exam = attrs.get("exam", getattr(self.instance, "exam", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        marks = attrs.get("marks", getattr(self.instance, "marks", None))
        is_absent = attrs.get("is_absent", getattr(self.instance, "is_absent", False))
        is_exempt = attrs.get("is_exempt", getattr(self.instance, "is_exempt", False))
        if exam and exam.status in [InternalExam.Status.FINALIZED, InternalExam.Status.PUBLISHED]:
            raise serializers.ValidationError("Finalized examination results are locked.")
        if subject and exam and not exam.subjects.filter(pk=subject.pk).exists() and exam.subject_id != subject.pk:
            raise serializers.ValidationError({"subject": "This subject is not part of the examination."})
        if student and exam:
            class_ids = set(exam.classes.values_list("id", flat=True))
            if exam.academic_class_id: class_ids.add(exam.academic_class_id)
            enrollment = attrs.get("enrollment", getattr(self.instance, "enrollment", None))
            if not enrollment and exam.academic_year_id:
                from apps.students.models import StudentEnrollment
                enrollment = StudentEnrollment.objects.filter(
                    madrasa=exam.madrasa,
                    student=student,
                    academic_year=exam.academic_year,
                    academic_class_id__in=class_ids,
                ).first()
            student_class_id = enrollment.academic_class_id if enrollment else student.current_class_id
            if student_class_id not in class_ids:
                raise serializers.ValidationError({"student": "This student is not in an examination class."})
        if is_absent and is_exempt:
            raise serializers.ValidationError("A result cannot be both absent and exempt.")
        paper = attrs.get("paper", getattr(self.instance, "paper", None))
        if paper and (not exam or not subject or paper.exam_id != exam.id or paper.subject_id != subject.id):
            raise serializers.ValidationError({"paper": "The selected paper does not match this exam and subject."})
        total_marks = paper.total_marks_snapshot if paper and paper.total_marks_snapshot is not None else subject.total_marks if subject else None
        passing_marks = paper.passing_marks_snapshot if paper and paper.passing_marks_snapshot is not None else subject.passing_marks if subject else None
        if is_exempt:
            attrs["marks"] = 0
            attrs["result"] = InternalExamResult.Result.PASS
        elif is_absent:
            attrs["marks"] = 0
            attrs["result"] = InternalExamResult.Result.FAIL
        elif marks is not None and total_marks is not None:
            if marks < 0 or marks > total_marks:
                raise serializers.ValidationError({"marks": f"Marks must be between 0 and {total_marks}."})
            attrs["result"] = InternalExamResult.Result.PASS if marks >= passing_marks else InternalExamResult.Result.FAIL
        return attrs

    class Meta:
        model = InternalExamResult
        fields = ["id", "exam", "exam_name", "exam_date", "paper", "subject", "subject_name", "total_marks", "passing_marks", "student", "student_name", "enrollment", "roll_number_snapshot", "marks", "result", "is_absent", "is_exempt", "remarks", "entered_by", "verified_by", "verified_at", "updated_at"]
        read_only_fields = ["result", "entered_by", "verified_by", "verified_at", "updated_at"]


class ExamDutySerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    paper_name = serializers.CharField(source="paper.subject.name", read_only=True)
    class Meta:
        model = ExamDuty
        fields = ["id", "exam", "paper", "paper_name", "staff", "staff_name", "duty_type", "room", "status", "assigned_by", "remarks"]
        read_only_fields = ["assigned_by"]

    def validate(self, attrs):
        exam = attrs.get("exam", getattr(self.instance, "exam", None))
        paper = attrs.get("paper", getattr(self.instance, "paper", None))
        if paper and paper.exam_id != exam.id:
            raise serializers.ValidationError({"paper": "The selected paper does not belong to this exam."})
        return attrs


class ExamAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.full_name", read_only=True)
    roll_number = serializers.CharField(source="enrollment.roll_number", read_only=True)
    class Meta:
        model = ExamAttendance
        fields = ["id", "paper", "enrollment", "student_name", "roll_number", "status", "seat_number", "room", "marked_by", "marked_at"]
        read_only_fields = ["marked_by", "marked_at"]

    def validate(self, attrs):
        paper = attrs.get("paper", getattr(self.instance, "paper", None))
        enrollment = attrs.get("enrollment", getattr(self.instance, "enrollment", None))
        exam = paper.exam if paper else None
        class_ids = set(exam.classes.values_list("id", flat=True)) if exam else set()
        if exam and exam.academic_class_id:
            class_ids.add(exam.academic_class_id)
        if enrollment and class_ids and enrollment.academic_class_id not in class_ids:
            raise serializers.ValidationError({"enrollment": "This enrollment is not in an examination class."})
        if enrollment and exam and exam.academic_year_id and enrollment.academic_year_id != exam.academic_year_id:
            raise serializers.ValidationError({"enrollment": "This enrollment is not in the examination academic year."})
        return attrs


class ExamResultChangeSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    class Meta:
        model = ExamResultChange
        fields = ["id", "result", "old_marks", "new_marks", "old_result", "new_result", "reason", "changed_by", "changed_by_name", "changed_at"]
        read_only_fields = fields
    def get_changed_by_name(self, change):
        return (change.changed_by.get_full_name() or change.changed_by.username) if change.changed_by else "سسٹم"


class AnnualResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.full_name", read_only=True)
    class_name = serializers.CharField(source="enrollment.academic_class.name", read_only=True)
    academic_year_name = serializers.CharField(source="enrollment.academic_year.name", read_only=True)
    class Meta:
        model = AnnualResult
        fields = ["id", "enrollment", "student_name", "class_name", "academic_year_name", "total_marks", "obtained_marks", "percentage", "grade", "rank", "result", "promotion_eligible", "finalized_by", "finalized_at", "created_at"]
        read_only_fields = fields


class WafaqBoardRegistrationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = WafaqBoardRegistration
        fields = ["id", "student", "student_name", "wafaq_name", "roll_number", "status"]


class WafaqResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="registration.student.full_name", read_only=True)

    class Meta:
        model = WafaqResult
        fields = ["id", "registration", "student_name", "passing_year", "result"]
