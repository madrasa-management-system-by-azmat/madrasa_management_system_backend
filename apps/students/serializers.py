from rest_framework import serializers

from apps.exams.models import WafaqResult
from apps.exams.serializers import InternalExamResultSerializer, WafaqBoardRegistrationSerializer, WafaqResultSerializer
from apps.finance.serializers import StudentFeeLogSerializer, StudentSponsorshipSerializer
from apps.hifz.serializers import HifzDailyLogSerializer
from apps.hostel.serializers import GatePassSerializer, HostelAllocationSerializer

from .models import AcademicClass, Department, Halaqa, Student, StudentAttendance


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class AcademicClassSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = AcademicClass
        fields = ["id", "name", "department", "department_name", "tuition_fee", "hostel_fee"]


class HalaqaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Halaqa
        fields = ["id", "name", "ustad_name"]


class StudentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="current_class.name", read_only=True)
    department_name = serializers.CharField(source="current_class.department.name", read_only=True)
    halaqa_name = serializers.CharField(source="current_halaqa.name", read_only=True)

    class Meta:
        model = Student
        fields = [
            "id",
            "registration_number",
            "full_name",
            "guardian_name",
            "guardian_relation",
            "guardian_cnic",
            "guardian_phone",
            "cnic",
            "phone",
            "nationality",
            "country",
            "religion",
            "caste",
            "gender",
            "date_of_birth",
            "residential_status",
            "is_mustahiq",
            "current_halaqa",
            "halaqa_name",
            "current_class",
            "class_name",
            "department_name",
            "admission_date",
            "requested_class",
            "current_address",
            "permanent_address",
            "health_conditions",
            "modern_education",
            "other_certificates",
            "previous_madrasas",
            "relatives",
            "admission_test_report",
            "office_notes",
            "admission_decision",
            "photo",
            "notes",
            "status",
            "created_at",
            "updated_at",
        ]


class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    registration_number = serializers.CharField(source="student.registration_number", read_only=True)
    class_name = serializers.CharField(source="student.current_class.name", read_only=True)

    class Meta:
        model = StudentAttendance
        fields = [
            "id", "student", "student_name", "registration_number", "class_name",
            "date", "status", "remarks",
        ]
        read_only_fields = [
            "id",
            "registration_number",
            "class_name",
            "department_name",
            "halaqa_name",
            "created_at",
            "updated_at",
        ]


class StudentOverviewSerializer(StudentSerializer):
    fee_logs = StudentFeeLogSerializer(many=True, read_only=True)
    sponsorships = StudentSponsorshipSerializer(many=True, read_only=True)
    internal_exam_results = InternalExamResultSerializer(many=True, read_only=True)
    wafaq_registrations = WafaqBoardRegistrationSerializer(many=True, read_only=True)
    hifz_logs = HifzDailyLogSerializer(many=True, read_only=True)
    hostel_allocations = HostelAllocationSerializer(many=True, read_only=True)
    gate_passes = GatePassSerializer(many=True, read_only=True)
    wafaq_results = serializers.SerializerMethodField()

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + [
            "fee_logs",
            "sponsorships",
            "internal_exam_results",
            "wafaq_registrations",
            "wafaq_results",
            "hifz_logs",
            "hostel_allocations",
            "gate_passes",
        ]

    def get_wafaq_results(self, student):
        results = WafaqResult.objects.filter(registration__student=student).select_related("registration__student")
        return WafaqResultSerializer(results, many=True).data
