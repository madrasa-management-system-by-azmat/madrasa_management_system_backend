from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import InstitutionCalendarDay, LeaveAttachment, LeaveAuditEvent, LeaveBalance, LeavePolicy, LeavePolicyRule, LeaveRequest, LeaveRequestDay, LeaveSubstitution, LeaveType


class InstitutionCalendarDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = InstitutionCalendarDay
        fields = ["id", "date", "day_type", "audience", "academic_class", "name", "counts_as_leave_day", "created_by"]
        read_only_fields = ["created_by"]


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "code", "name", "subject_kind", "is_paid", "paid_percentage", "requires_attachment", "attachment_required_after_days", "allow_half_day", "allow_negative_balance", "requires_substitution", "attendance_status", "is_active"]


class LeavePolicyRuleSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeavePolicyRule
        fields = ["id", "leave_type", "leave_type_name", "annual_entitlement", "maximum_consecutive_days", "minimum_notice_days", "carry_forward_limit"]


class LeavePolicySerializer(serializers.ModelSerializer):
    rules = LeavePolicyRuleSerializer(many=True, read_only=True)

    class Meta:
        model = LeavePolicy
        fields = ["id", "name", "subject_kind", "effective_from", "effective_to", "working_weekdays", "is_default", "is_active", "created_by", "rules"]
        read_only_fields = ["created_by"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    subject_name = serializers.SerializerMethodField()
    available = serializers.DecimalField(max_digits=7, decimal_places=2, read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ["id", "staff", "student", "subject_name", "leave_type", "leave_type_name", "year", "opening", "entitlement", "used", "adjusted", "available"]

    def get_subject_name(self, balance):
        return balance.staff.full_name if balance.staff_id else balance.student.full_name


class LeaveRequestDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequestDay
        fields = ["id", "date", "units", "is_chargeable", "calendar_day"]


class LeaveSubstitutionSerializer(serializers.ModelSerializer):
    substitute_name = serializers.CharField(source="substitute_staff.full_name", read_only=True)
    assignment_label = serializers.SerializerMethodField()

    class Meta:
        model = LeaveSubstitution
        fields = ["id", "request", "date", "teaching_assignment", "assignment_label", "substitute_staff", "substitute_name", "notes", "assigned_by"]
        read_only_fields = ["assigned_by"]

    def get_assignment_label(self, item):
        assignment = item.teaching_assignment
        return f"{assignment.academic_class.name} — {assignment.subject.name}" if assignment else ""


class LeaveAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveAttachment
        fields = ["id", "request", "file", "original_name", "uploaded_by", "uploaded_at"]
        read_only_fields = ["original_name", "uploaded_by", "uploaded_at"]

    def validate_file(self, upload):
        if upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Attachment size cannot exceed 10 MB.")
        return upload


class LeaveAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveAuditEvent
        fields = ["id", "action", "from_status", "to_status", "actor", "actor_name", "comment", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, event):
        return (event.actor.get_full_name() or event.actor.username) if event.actor else "سسٹم"


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    subject_name = serializers.SerializerMethodField()
    days = LeaveRequestDaySerializer(many=True, read_only=True)
    substitutions = LeaveSubstitutionSerializer(many=True, read_only=True)
    attachments = LeaveAttachmentSerializer(many=True, read_only=True)
    audit_events = LeaveAuditEventSerializer(many=True, read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ["id", "request_number", "subject_kind", "staff", "student", "guardian", "subject_name", "leave_type", "leave_type_name", "starts_on", "ends_on", "day_part", "chargeable_days", "reason", "contact_during_leave", "status", "submitted_by", "submitted_at", "approved_by", "approved_at", "rejected_by", "rejected_at", "decision_notes", "cancellation_reason", "cancelled_by", "cancelled_at", "created_at", "updated_at", "days", "substitutions", "attachments", "audit_events"]
        read_only_fields = ["request_number", "guardian", "chargeable_days", "status", "submitted_by", "submitted_at", "approved_by", "approved_at", "rejected_by", "rejected_at", "decision_notes", "cancellation_reason", "cancelled_by", "cancelled_at", "created_at", "updated_at"]

    def get_subject_name(self, request):
        return request.staff.full_name if request.staff_id else request.student.full_name

    def validate(self, attrs):
        attrs = super().validate(attrs)
        kind = attrs.get("subject_kind", getattr(self.instance, "subject_kind", None))
        staff = attrs.get("staff", getattr(self.instance, "staff", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        leave_type = attrs.get("leave_type", getattr(self.instance, "leave_type", None))
        start = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        end = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        day_part = attrs.get("day_part", getattr(self.instance, "day_part", LeaveRequest.DayPart.FULL))
        if kind == LeaveRequest.SubjectKind.STAFF and (not staff or student):
            raise serializers.ValidationError("Select exactly one staff member for staff leave.")
        if kind == LeaveRequest.SubjectKind.STUDENT and (not student or staff):
            raise serializers.ValidationError("Select exactly one student for student leave.")
        if leave_type and leave_type.subject_kind not in [kind, LeaveType.SubjectKind.BOTH]:
            raise serializers.ValidationError({"leave_type": "This leave type does not apply to the selected subject."})
        if start and end and end < start:
            raise serializers.ValidationError({"ends_on": "End date cannot precede start date."})
        if start and end and day_part != LeaveRequest.DayPart.FULL and start != end:
            raise serializers.ValidationError({"day_part": "Half-day leave must use one date."})
        if leave_type and day_part != LeaveRequest.DayPart.FULL and not leave_type.allow_half_day:
            raise serializers.ValidationError({"day_part": "This leave type does not allow half days."})
        tenant = self.context["request"].user.profile.madrasa
        for related in [staff, student, leave_type]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        overlap = LeaveRequest.objects.filter(madrasa=tenant, starts_on__lte=end, ends_on__gte=start).exclude(status__in=[LeaveRequest.Status.REJECTED, LeaveRequest.Status.CANCELLED])
        overlap = overlap.filter(staff=staff) if staff else overlap.filter(student=student)
        if self.instance:
            overlap = overlap.exclude(pk=self.instance.pk)
        if overlap.exists():
            raise serializers.ValidationError("An overlapping leave request already exists.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tenant = validated_data.pop("madrasa", self.context["request"].user.profile.madrasa)
        request = LeaveRequest.objects.create(madrasa=tenant, request_number=LeaveRequest.issue_number(tenant), submitted_by=self.context["request"].user, **validated_data)
        self._rebuild_days(request)
        LeaveAuditEvent.objects.create(madrasa=tenant, request=request, action="created", to_status=request.status, actor=self.context["request"].user)
        return request

    @staticmethod
    def _rebuild_days(request):
        request.days.all().delete()
        current = request.starts_on
        chargeable = Decimal("0")
        while current <= request.ends_on:
            audience = InstitutionCalendarDay.Audience.STAFF if request.subject_kind == LeaveRequest.SubjectKind.STAFF else InstitutionCalendarDay.Audience.STUDENTS
            calendar = InstitutionCalendarDay.objects.filter(madrasa=request.madrasa, date=current).filter(Q(audience=InstitutionCalendarDay.Audience.ALL) | Q(audience=audience)).first()
            default_working = current.weekday() < 6
            is_chargeable = calendar.counts_as_leave_day if calendar else default_working
            units = Decimal("0.5") if request.day_part != LeaveRequest.DayPart.FULL else Decimal("1")
            if not is_chargeable:
                units = Decimal("0")
            LeaveRequestDay.objects.create(madrasa=request.madrasa, request=request, date=current, units=units, is_chargeable=is_chargeable, calendar_day=calendar)
            chargeable += units
            current += timedelta(days=1)
        request.chargeable_days = chargeable
        request.save(update_fields=["chargeable_days", "updated_at"])
