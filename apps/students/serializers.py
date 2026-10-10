from rest_framework import serializers

from apps.exams.models import WafaqResult
from apps.exams.serializers import InternalExamResultSerializer, WafaqBoardRegistrationSerializer, WafaqResultSerializer
from apps.finance.serializers import StudentMonthlyFeeSerializer, StudentSponsorshipSerializer
from apps.hifz.serializers import HifzDailyLogSerializer
from apps.hostel.serializers import GatePassSerializer, HostelAllocationSerializer

from .models import (
    AcademicClass,
    AcademicYear,
    AdmissionApplication,
    AdmissionDecision,
    AdmissionInterview,
    AdmissionTest,
    AlumniProfile,
    Department,
    GraduationRecord,
    Halaqa,
    PromotionDecision,
    Student,
    StudentAttendance,
    StudentEnrollment,
    StudentLifecycleEvent,
    RollNumberChange,
    AttendanceAlert,
    AttendanceAlertRule,
)


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
            "lifecycle_status",
            "application_date",
            "admitted_at",
            "graduation_date",
            "alumni_since",
            "archived_at",
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


class AttendanceAlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceAlertRule
        fields = ["id", "consecutive_absence_threshold", "monthly_absence_threshold", "monthly_late_threshold", "is_active", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class AttendanceAlertSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    registration_number = serializers.CharField(source="student.registration_number", read_only=True)
    class_name = serializers.CharField(source="student.current_class.name", read_only=True)
    alert_type_label = serializers.CharField(source="get_alert_type_display", read_only=True)
    severity_label = serializers.CharField(source="get_severity_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    acknowledged_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceAlert
        fields = ["id", "student", "student_name", "registration_number", "class_name", "alert_type", "alert_type_label", "period_key", "count", "date_from", "date_to", "severity", "severity_label", "status", "status_label", "reason", "details", "acknowledged_by", "acknowledged_by_name", "acknowledged_at", "resolved_by", "resolved_by_name", "resolved_at", "resolution_notes", "created_at", "updated_at"]
        read_only_fields = fields

    def get_acknowledged_by_name(self, alert):
        return (alert.acknowledged_by.get_full_name() or alert.acknowledged_by.username) if alert.acknowledged_by else ""

    def get_resolved_by_name(self, alert):
        return (alert.resolved_by.get_full_name() or alert.resolved_by.username) if alert.resolved_by else ""
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
    monthly_fees = StudentMonthlyFeeSerializer(many=True, read_only=True)
    sponsorships = StudentSponsorshipSerializer(many=True, read_only=True)
    internal_exam_results = InternalExamResultSerializer(many=True, read_only=True)
    wafaq_registrations = WafaqBoardRegistrationSerializer(many=True, read_only=True)
    hifz_logs = HifzDailyLogSerializer(many=True, read_only=True)
    hostel_allocations = HostelAllocationSerializer(many=True, read_only=True)
    gate_passes = GatePassSerializer(many=True, read_only=True)
    wafaq_results = serializers.SerializerMethodField()
    lifecycle_events = serializers.SerializerMethodField()
    enrollments = serializers.SerializerMethodField()

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + [
            "monthly_fees",
            "sponsorships",
            "internal_exam_results",
            "wafaq_registrations",
            "wafaq_results",
            "hifz_logs",
            "hostel_allocations",
            "gate_passes",
            "lifecycle_events",
            "enrollments",
        ]

    def get_wafaq_results(self, student):
        results = WafaqResult.objects.filter(registration__student=student).select_related("registration__student")
        return WafaqResultSerializer(results, many=True).data

    def get_lifecycle_events(self, student):
        return StudentLifecycleEventSerializer(student.lifecycle_events.all(), many=True).data

    def get_enrollments(self, student):
        return StudentEnrollmentSerializer(student.enrollments.all(), many=True).data


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ["id", "name", "starts_on", "ends_on", "is_current", "status"]


class StudentEnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    registration_number = serializers.CharField(source="student.registration_number", read_only=True)
    guardian_name = serializers.CharField(source="student.guardian_name", read_only=True)
    photo = serializers.ImageField(source="student.photo", read_only=True)
    academic_year_name = serializers.CharField(source="academic_year.name", read_only=True)
    class_name = serializers.CharField(source="academic_class.name", read_only=True)
    halaqa_name = serializers.CharField(source="halaqa.name", read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = ["id", "student", "student_name", "registration_number", "guardian_name", "photo", "academic_year", "academic_year_name", "academic_class", "class_name", "halaqa", "halaqa_name", "roll_number", "started_on", "ended_on", "status", "previous_enrollment", "created_at"]
        read_only_fields = ["roll_number", "created_at"]


class RollNumberChangeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="enrollment.student.full_name", read_only=True)
    registration_number = serializers.CharField(source="enrollment.student.registration_number", read_only=True)
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RollNumberChange
        fields = ["id", "enrollment", "student_name", "registration_number", "old_roll_number", "new_roll_number", "reason", "changed_by", "changed_by_name", "changed_at"]
        read_only_fields = fields

    def get_changed_by_name(self, change):
        if not change.changed_by:
            return "سسٹم"
        return change.changed_by.get_full_name() or change.changed_by.username


class StudentLifecycleEventSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.CharField(source="get_to_status_display", read_only=True)

    class Meta:
        model = StudentLifecycleEvent
        fields = ["id", "student", "from_status", "from_status_label", "to_status", "to_status_label", "effective_at", "reason", "notes", "performed_by", "performed_by_name", "metadata", "created_at"]
        read_only_fields = ["performed_by", "created_at"]

    def get_performed_by_name(self, event):
        if not event.performed_by:
            return "سسٹم"
        return event.performed_by.get_full_name() or event.performed_by.username

    def get_from_status_label(self, event):
        return dict(Student.LifecycleStatus.choices).get(event.from_status, event.from_status)


class AdmissionInterviewSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionInterview
        fields = ["id", "application", "scheduled_at", "completed_at", "interviewer", "interviewer_name", "attendance_status", "score", "recommendation", "notes", "created_at"]
        read_only_fields = ["interviewer", "created_at"]

    def get_interviewer_name(self, interview):
        return (interview.interviewer.get_full_name() or interview.interviewer.username) if interview.interviewer else ""


class AdmissionTestSerializer(serializers.ModelSerializer):
    evaluator_name = serializers.SerializerMethodField()

    class Meta:
        model = AdmissionTest
        fields = ["id", "application", "scheduled_at", "completed_at", "evaluator", "evaluator_name", "total_marks", "obtained_marks", "passing_marks", "outcome", "attempt_number", "report", "created_at"]
        read_only_fields = ["evaluator", "created_at"]

    def validate(self, attrs):
        obtained = attrs.get("obtained_marks", getattr(self.instance, "obtained_marks", None))
        total = attrs.get("total_marks", getattr(self.instance, "total_marks", None))
        if obtained is not None and total is not None and obtained > total:
            raise serializers.ValidationError({"obtained_marks": "Obtained marks cannot exceed total marks."})
        return attrs

    def get_evaluator_name(self, test):
        return (test.evaluator.get_full_name() or test.evaluator.username) if test.evaluator else ""


class AdmissionDecisionSerializer(serializers.ModelSerializer):
    decided_by_name = serializers.SerializerMethodField()
    approved_class_name = serializers.CharField(source="approved_class.name", read_only=True)

    class Meta:
        model = AdmissionDecision
        fields = ["id", "application", "decision", "decided_at", "decided_by", "decided_by_name", "approved_class", "approved_class_name", "conditions", "notes"]
        read_only_fields = ["decided_by"]

    def get_decided_by_name(self, decision):
        return (decision.decided_by.get_full_name() or decision.decided_by.username) if decision.decided_by else ""


class AdmissionApplicationSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    requested_class_name = serializers.CharField(source="requested_class.name", read_only=True)
    interviews = AdmissionInterviewSerializer(many=True, read_only=True)
    tests = AdmissionTestSerializer(many=True, read_only=True)
    decisions = AdmissionDecisionSerializer(many=True, read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = ["id", "application_number", "application_date", "full_name", "father_name", "mother_name", "guardian_name", "guardian_relation", "guardian_phone", "alternate_phone", "date_of_birth", "gender", "address", "village", "tehsil", "district", "previous_institution", "previous_education", "requested_class", "requested_class_name", "special_education_needs", "emergency_contact", "source", "notes", "status", "student", "interviews", "tests", "decisions", "created_at", "updated_at"]
        read_only_fields = ["application_number", "student", "created_at", "updated_at"]

    def to_internal_value(self, data):
        if data.get("date_of_birth") == "":
            data = data.copy()
            data["date_of_birth"] = None
        return super().to_internal_value(data)


class GraduationRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = GraduationRecord
        fields = ["id", "student", "student_name", "enrollment", "completion_date", "final_result", "distinction", "graduation_number", "approved_by", "approved_at", "notes"]
        read_only_fields = ["approved_by", "approved_at"]


class AlumniProfileSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = AlumniProfile
        fields = ["id", "student", "student_name", "graduation_record", "alumni_since", "current_phone", "email", "current_address", "occupation", "employer", "further_education", "contact_consent", "notes"]


class PromotionDecisionSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = PromotionDecision
        fields = ["id", "student", "student_name", "from_enrollment", "target_class", "target_academic_year", "decision", "decided_on", "decided_by", "reason", "notes", "applied_at"]
        read_only_fields = ["decided_by", "applied_at"]
