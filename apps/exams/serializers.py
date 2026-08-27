from rest_framework import serializers

from .models import InternalExam, InternalExamPaper, InternalExamResult, WafaqBoardRegistration, WafaqResult


class InternalExamPaperSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    academic_class = serializers.IntegerField(source="subject.academic_class_id", read_only=True)
    class_name = serializers.CharField(source="subject.academic_class.name", read_only=True)

    class Meta:
        model = InternalExamPaper
        fields = ["id", "subject", "subject_name", "academic_class", "class_name", "paper_date", "paper_time"]


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

    def create(self, validated_data):
        papers = validated_data.pop("papers", [])
        exam = super().create(validated_data)
        tenant = self.context["request"].user.profile.madrasa
        for paper in papers:
            InternalExamPaper.objects.create(exam=exam, madrasa=tenant, **paper)
        return exam

    def update(self, instance, validated_data):
        papers = validated_data.pop("papers", None)
        exam = super().update(instance, validated_data)
        if papers is not None:
            exam.papers.all().delete()
            tenant = self.context["request"].user.profile.madrasa
            for paper in papers:
                InternalExamPaper.objects.create(exam=exam, madrasa=tenant, **paper)
        return exam

    class Meta:
        model = InternalExam
        fields = ["id", "name", "academic_class", "class_name", "classes", "class_names", "subject", "subject_name", "subjects", "subject_names", "papers", "exam_date"]


class InternalExamResultSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)
    exam_date = serializers.DateField(source="exam.exam_date", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    total_marks = serializers.IntegerField(source="subject.total_marks", read_only=True)
    passing_marks = serializers.IntegerField(source="subject.passing_marks", read_only=True)

    class Meta:
        model = InternalExamResult
        fields = ["id", "exam", "exam_name", "exam_date", "subject", "subject_name", "total_marks", "passing_marks", "student", "student_name", "marks", "result"]


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
