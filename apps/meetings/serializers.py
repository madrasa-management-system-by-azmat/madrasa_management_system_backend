from django.db import transaction
from rest_framework import serializers

from .models import Meeting, MeetingActionItem, MeetingAgendaItem, MeetingAttachment, MeetingAuditEvent, MeetingDecision, MeetingMinutesRevision, MeetingParticipant, MeetingType


class MeetingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingType
        fields = ["id", "name", "code", "description", "default_duration_minutes", "default_quorum", "requires_approval", "is_confidential", "is_active", "sort_order"]


class MeetingAgendaItemSerializer(serializers.ModelSerializer):
    presenter_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetingAgendaItem
        fields = ["id", "meeting", "sequence", "title", "description", "presenter", "presenter_name", "allocated_minutes", "item_type", "status", "notes"]

    def get_presenter_name(self, item):
        return (item.presenter.get_full_name() or item.presenter.username) if item.presenter else ""


class MeetingParticipantSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = MeetingParticipant
        fields = ["id", "meeting", "user", "staff", "external_name", "external_email", "display_name", "participant_role", "invitation_status", "attendance_status", "response_comment", "attendance_notes", "invited_at", "responded_at", "check_in_at", "check_out_at", "marked_by", "marked_at", "minutes_acknowledged_at"]
        read_only_fields = ["invited_at", "responded_at", "marked_by", "marked_at", "minutes_acknowledged_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        identities = [bool(attrs.get("user")), bool(attrs.get("staff")), bool(attrs.get("external_name"))]
        if self.instance:
            identities = [bool(attrs.get("user", self.instance.user)), bool(attrs.get("staff", self.instance.staff)), bool(attrs.get("external_name", self.instance.external_name))]
        if sum(identities) != 1:
            raise serializers.ValidationError("Provide exactly one participant identity: user, staff, or external name.")
        tenant = self.context["request"].user.profile.madrasa
        user = attrs.get("user", getattr(self.instance, "user", None))
        staff = attrs.get("staff", getattr(self.instance, "staff", None))
        if user and getattr(getattr(user, "profile", None), "madrasa_id", None) != tenant.id:
            raise serializers.ValidationError({"user": "Participant must belong to the active madrasa."})
        if staff and staff.madrasa_id != tenant.id:
            raise serializers.ValidationError({"staff": "Participant must belong to the active madrasa."})
        return attrs


class MeetingMinutesRevisionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetingMinutesRevision
        fields = ["id", "meeting", "version", "title", "content", "summary", "discussion_notes", "attendance_snapshot", "agenda_snapshot", "based_on", "status", "is_current", "created_by", "created_by_name", "created_at", "submitted_at", "approved_by", "approved_at", "approval_comment"]
        read_only_fields = ["version", "attendance_snapshot", "agenda_snapshot", "status", "is_current", "created_by", "created_at", "submitted_at", "approved_by", "approved_at", "approval_comment"]

    def get_created_by_name(self, item):
        return (item.created_by.get_full_name() or item.created_by.username) if item.created_by else "سسٹم"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        meeting = attrs.get("meeting", getattr(self.instance, "meeting", None))
        based_on = attrs.get("based_on", getattr(self.instance, "based_on", None))
        if based_on and meeting and based_on.meeting_id != meeting.id:
            raise serializers.ValidationError({"based_on": "Base revision must belong to the same meeting."})
        return attrs


class MeetingDecisionSerializer(serializers.ModelSerializer):
    agenda_title = serializers.CharField(source="agenda_item.title", read_only=True)
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetingDecision
        fields = ["id", "meeting", "agenda_item", "agenda_title", "decision_number", "title", "decision_text", "rationale", "status", "effective_date", "is_confidential", "proposed_by", "approved_by", "approved_by_name", "approved_at", "created_at"]
        read_only_fields = ["decision_number", "status", "proposed_by", "approved_by", "approved_at", "created_at"]

    def get_approved_by_name(self, item):
        return (item.approved_by.get_full_name() or item.approved_by.username) if item.approved_by else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        meeting = attrs.get("meeting", getattr(self.instance, "meeting", None))
        agenda_item = attrs.get("agenda_item", getattr(self.instance, "agenda_item", None))
        if agenda_item and meeting and agenda_item.meeting_id != meeting.id:
            raise serializers.ValidationError({"agenda_item": "Agenda item must belong to the same meeting."})
        return attrs


class MeetingActionItemSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    decision_title = serializers.CharField(source="decision.title", read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = MeetingActionItem
        fields = ["id", "meeting", "decision", "decision_title", "title", "description", "owner", "owner_name", "due_date", "priority", "status", "progress_percentage", "completion_notes", "completed_at", "created_by", "created_at", "updated_at", "is_overdue"]
        read_only_fields = ["completed_at", "created_by", "created_at", "updated_at"]

    def get_owner_name(self, item):
        return item.owner.get_full_name() or item.owner.username

    def get_is_overdue(self, item):
        from django.utils import timezone
        return bool(item.due_date and item.due_date < timezone.localdate() and item.status not in [MeetingActionItem.Status.COMPLETED, MeetingActionItem.Status.CANCELLED])

    def validate(self, attrs):
        attrs = super().validate(attrs)
        meeting = attrs.get("meeting", getattr(self.instance, "meeting", None))
        decision = attrs.get("decision", getattr(self.instance, "decision", None))
        progress = attrs.get("progress_percentage", getattr(self.instance, "progress_percentage", 0))
        if progress > 100:
            raise serializers.ValidationError({"progress_percentage": "Progress cannot exceed 100%."})
        if decision and meeting and decision.meeting_id != meeting.id:
            raise serializers.ValidationError({"decision": "Decision must belong to the same meeting."})
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        tenant = self.context["request"].user.profile.madrasa
        if owner and getattr(getattr(owner, "profile", None), "madrasa_id", None) != tenant.id:
            raise serializers.ValidationError({"owner": "Owner must belong to the active madrasa."})
        return attrs


class MeetingAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = MeetingAuditEvent
        fields = ["id", "meeting", "action", "from_status", "to_status", "actor", "actor_name", "comment", "metadata", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, item):
        return (item.actor.get_full_name() or item.actor.username) if item.actor else "سسٹم"


class MeetingAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingAttachment
        fields = ["id", "meeting", "agenda_item", "file", "original_name", "description", "uploaded_by", "uploaded_at"]
        read_only_fields = ["original_name", "uploaded_by", "uploaded_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        meeting = attrs.get("meeting", getattr(self.instance, "meeting", None))
        agenda = attrs.get("agenda_item", getattr(self.instance, "agenda_item", None))
        if agenda and meeting and agenda.meeting_id != meeting.id:
            raise serializers.ValidationError({"agenda_item": "Agenda item must belong to the same meeting."})
        upload = attrs.get("file")
        if upload and upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError({"file": "Attachment size cannot exceed 10 MB."})
        return attrs


class MeetingListSerializer(serializers.ModelSerializer):
    meeting_type_name = serializers.CharField(source="meeting_type.name", read_only=True)
    chairperson_name = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(source="participants.count", read_only=True)
    action_count = serializers.IntegerField(source="action_items.count", read_only=True)

    class Meta:
        model = Meeting
        fields = ["id", "meeting_number", "meeting_type", "meeting_type_name", "title", "description", "status", "visibility", "scheduled_start", "scheduled_end", "actual_start", "actual_end", "venue", "online_url", "chairperson", "chairperson_name", "secretary", "approver", "quorum_required", "quorum_met", "participant_count", "action_count", "finalized_at", "created_at", "updated_at"]

    def get_chairperson_name(self, meeting):
        return (meeting.chairperson.get_full_name() or meeting.chairperson.username) if meeting.chairperson else ""


class MeetingDetailSerializer(MeetingListSerializer):
    agenda_items = MeetingAgendaItemSerializer(many=True, read_only=True)
    participants = MeetingParticipantSerializer(many=True, read_only=True)
    minutes_revisions = MeetingMinutesRevisionSerializer(many=True, read_only=True)
    decisions = MeetingDecisionSerializer(many=True, read_only=True)
    action_items = MeetingActionItemSerializer(many=True, read_only=True)
    audit_events = MeetingAuditEventSerializer(many=True, read_only=True)
    attachments = MeetingAttachmentSerializer(many=True, read_only=True)

    class Meta(MeetingListSerializer.Meta):
        fields = MeetingListSerializer.Meta.fields + ["agenda_items", "participants", "minutes_revisions", "decisions", "action_items", "audit_events", "attachments", "cancellation_reason", "created_by", "updated_by"]
        read_only_fields = ["meeting_number", "status", "actual_start", "actual_end", "quorum_met", "finalized_at", "created_by", "updated_by"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status in [Meeting.Status.FINALIZED, Meeting.Status.CANCELLED, Meeting.Status.ARCHIVED]:
            raise serializers.ValidationError("Finalized, cancelled, or archived meetings are locked.")
        start = attrs.get("scheduled_start", getattr(self.instance, "scheduled_start", None))
        end = attrs.get("scheduled_end", getattr(self.instance, "scheduled_end", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"scheduled_end": "Meeting end must be later than start."})
        tenant = self.context["request"].user.profile.madrasa
        for related in [attrs.get("meeting_type"), *[attrs.get(name) for name in ["chairperson", "secretary", "approver"]]]:
            related_tenant = getattr(related, "madrasa_id", None) or getattr(getattr(related, "profile", None), "madrasa_id", None)
            if related and related_tenant != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        return attrs

    def create(self, validated_data):
        tenant = validated_data.pop("madrasa", self.context["request"].user.profile.madrasa)
        year, number, meeting_number = Meeting.issue_number(tenant)
        meeting = Meeting.objects.create(madrasa=tenant, sequence_year=year, sequence_number=number, meeting_number=meeting_number, created_by=self.context["request"].user, updated_by=self.context["request"].user, **validated_data)
        MeetingAuditEvent.objects.create(madrasa=tenant, meeting=meeting, action="created", to_status=meeting.status, actor=self.context["request"].user)
        return meeting
