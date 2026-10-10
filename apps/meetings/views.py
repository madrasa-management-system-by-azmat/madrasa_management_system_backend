from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import Meeting, MeetingActionItem, MeetingAgendaItem, MeetingAttachment, MeetingAuditEvent, MeetingDecision, MeetingMinutesRevision, MeetingParticipant, MeetingType
from .serializers import MeetingActionItemSerializer, MeetingAgendaItemSerializer, MeetingAttachmentSerializer, MeetingAuditEventSerializer, MeetingDecisionSerializer, MeetingDetailSerializer, MeetingListSerializer, MeetingMinutesRevisionSerializer, MeetingParticipantSerializer, MeetingTypeSerializer


class MeetingBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Meetings"])
class MeetingTypeViewSet(MeetingBaseViewSet):
    queryset = MeetingType.objects.all()
    serializer_class = MeetingTypeSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "name"]


@extend_schema(tags=["Meetings"])
class MeetingViewSet(MeetingBaseViewSet):
    queryset = Meeting.objects.select_related("meeting_type", "chairperson", "secretary", "approver", "finalized_by").prefetch_related("agenda_items", "participants__user", "participants__staff", "minutes_revisions", "decisions", "action_items__owner", "audit_events__actor", "attachments")
    search_fields = ["meeting_number", "title", "description", "venue", "agenda_items__title", "decisions__title", "decisions__decision_text"]
    ordering_fields = ["scheduled_start", "status", "created_at", "updated_at"]

    def get_serializer_class(self):
        return MeetingDetailSerializer if self.action in ["retrieve", "create", "update", "partial_update"] else MeetingListSerializer

    def get_queryset(self):
        queryset = super().get_queryset().distinct()
        for field in ["status", "meeting_type", "visibility", "chairperson", "secretary", "approver"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        if self.request.query_params.get("upcoming") == "true":
            queryset = queryset.filter(scheduled_start__gte=timezone.now(), status=Meeting.Status.SCHEDULED)
        return queryset

    def perform_update(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.status != Meeting.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft meetings can be deleted.")
        super().perform_destroy(instance)

    def _event(self, meeting, action_name, old_status, comment="", metadata=None):
        MeetingAuditEvent.objects.create(madrasa=self.get_madrasa(), meeting=meeting, action=action_name, from_status=old_status, to_status=meeting.status, actor=self.request.user, comment=comment, metadata=metadata or {})

    def _transition(self, meeting, allowed, target, action_name, comment="", fields=None):
        if meeting.status not in allowed:
            return Response({"detail": "This workflow action is not allowed in the current state."}, status=status.HTTP_400_BAD_REQUEST)
        old = meeting.status
        meeting.status = target
        meeting.updated_by = self.request.user
        update_fields = ["status", "updated_by", "updated_at"]
        for key, value in (fields or {}).items():
            setattr(meeting, key, value)
            update_fields.append(key)
        meeting.save(update_fields=update_fields)
        self._event(meeting, action_name, old, comment)
        return Response(MeetingDetailSerializer(meeting, context={"request": self.request}).data)

    @action(detail=False, methods=["get"])
    def people_lookup(self, request):
        from apps.staff.models import Staff
        from apps.users.models import UserProfile
        users = UserProfile.objects.filter(madrasa=self.get_madrasa(), user__is_active=True).select_related("user")
        staff = Staff.objects.filter(madrasa=self.get_madrasa(), is_active=True).values("id", "full_name", "role")
        return Response({"users": [{"id": item.user_id, "name": item.user.get_full_name() or item.user.username, "role": item.role} for item in users], "staff": list(staff)})

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        meeting = self.get_object()
        if not meeting.agenda_items.exists() or not meeting.participants.exists():
            return Response({"detail": "Add agenda items and participants before scheduling."}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(meeting, [Meeting.Status.DRAFT], Meeting.Status.SCHEDULED, "scheduled", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def mark_held(self, request, pk=None):
        meeting = self.get_object()
        present_statuses = [MeetingParticipant.AttendanceStatus.PRESENT, MeetingParticipant.AttendanceStatus.LATE, MeetingParticipant.AttendanceStatus.REMOTE]
        present = meeting.participants.filter(attendance_status__in=present_statuses).count()
        if meeting.participants.filter(attendance_status=MeetingParticipant.AttendanceStatus.UNMARKED).exists():
            return Response({"detail": "Mark attendance for every participant first."}, status=status.HTTP_400_BAD_REQUEST)
        actual_start = request.data.get("actual_start") or meeting.scheduled_start
        actual_end = request.data.get("actual_end") or timezone.now()
        return self._transition(meeting, [Meeting.Status.SCHEDULED], Meeting.Status.HELD, "held", request.data.get("comment", ""), {"actual_start": actual_start, "actual_end": actual_end, "quorum_met": present >= meeting.quorum_required})

    @action(detail=True, methods=["post"])
    def start_minutes(self, request, pk=None):
        return self._transition(self.get_object(), [Meeting.Status.HELD, Meeting.Status.CHANGES_REQUESTED], Meeting.Status.MINUTES_DRAFT, "minutes_started", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def submit_minutes(self, request, pk=None):
        meeting = self.get_object()
        current = meeting.minutes_revisions.filter(is_current=True).first()
        if not current or not current.content.strip():
            return Response({"detail": "Create meeting minutes before submission."}, status=status.HTTP_400_BAD_REQUEST)
        if meeting.meeting_type.requires_approval and not meeting.approver_id:
            return Response({"detail": "Assign an approver before submitting minutes."}, status=status.HTTP_400_BAD_REQUEST)
        current.status = MeetingMinutesRevision.Status.SUBMITTED
        current.submitted_at = timezone.now()
        current.save(update_fields=["status", "submitted_at"])
        return self._transition(meeting, [Meeting.Status.MINUTES_DRAFT], Meeting.Status.PENDING_APPROVAL, "minutes_submitted", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def request_changes(self, request, pk=None):
        meeting = self.get_object()
        if self.request.user.profile.role != "admin" and meeting.approver_id != self.request.user.id:
            return Response({"detail": "Only the assigned approver can request changes."}, status=status.HTTP_403_FORBIDDEN)
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["A reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        current = meeting.minutes_revisions.filter(is_current=True).first()
        if current:
            current.status = MeetingMinutesRevision.Status.CHANGES_REQUESTED
            current.approval_comment = comment
            current.save(update_fields=["status", "approval_comment"])
        return self._transition(meeting, [Meeting.Status.PENDING_APPROVAL], Meeting.Status.CHANGES_REQUESTED, "changes_requested", comment)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def finalize(self, request, pk=None):
        meeting = self.get_object()
        if self.request.user.profile.role != "admin" and meeting.approver_id != self.request.user.id:
            return Response({"detail": "Only the assigned approver can finalize minutes."}, status=status.HTTP_403_FORBIDDEN)
        if meeting.status != Meeting.Status.PENDING_APPROVAL:
            return Response({"detail": "Submit minutes for approval first."}, status=status.HTTP_400_BAD_REQUEST)
        if meeting.quorum_met is False:
            return Response({"detail": "Meeting quorum was not met."}, status=status.HTTP_400_BAD_REQUEST)
        current = meeting.minutes_revisions.filter(is_current=True).first()
        if not current:
            return Response({"detail": "Current minutes revision not found."}, status=status.HTTP_400_BAD_REQUEST)
        current.status = MeetingMinutesRevision.Status.APPROVED
        current.approved_by = request.user
        current.approved_at = timezone.now()
        current.approval_comment = request.data.get("comment", "")
        current.save(update_fields=["status", "approved_by", "approved_at", "approval_comment"])
        meeting.decisions.filter(status=MeetingDecision.Status.PROPOSED).update(status=MeetingDecision.Status.APPROVED, approved_by=request.user, approved_at=timezone.now())
        return self._transition(meeting, [Meeting.Status.PENDING_APPROVAL], Meeting.Status.FINALIZED, "finalized", request.data.get("comment", ""), {"finalized_at": timezone.now(), "finalized_by": request.user})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        meeting = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"reason": ["Cancellation reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(meeting, [Meeting.Status.DRAFT, Meeting.Status.SCHEDULED], Meeting.Status.CANCELLED, "cancelled", reason, {"cancellation_reason": reason})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can archive meetings."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(self.get_object(), [Meeting.Status.FINALIZED, Meeting.Status.CANCELLED], Meeting.Status.ARCHIVED, "archived", request.data.get("comment", ""))


@extend_schema(tags=["Meetings"])
class MeetingAgendaItemViewSet(MeetingBaseViewSet):
    queryset = MeetingAgendaItem.objects.select_related("meeting", "presenter")
    serializer_class = MeetingAgendaItemSerializer
    search_fields = ["meeting__meeting_number", "meeting__title", "title", "description"]
    ordering_fields = ["sequence", "status"]

    def perform_create(self, serializer):
        meeting = serializer.validated_data["meeting"]
        if meeting.status != Meeting.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Agenda items can only be added to draft meetings.")
        super().perform_create(serializer)

    def perform_update(self, serializer):
        if serializer.instance.meeting.status != Meeting.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Scheduled meeting agendas are locked.")
        super().perform_update(serializer)


@extend_schema(tags=["Meetings"])
class MeetingParticipantViewSet(MeetingBaseViewSet):
    queryset = MeetingParticipant.objects.select_related("meeting", "user", "staff", "marked_by")
    serializer_class = MeetingParticipantSerializer
    search_fields = ["meeting__meeting_number", "meeting__title", "user__username", "user__first_name", "staff__full_name", "external_name"]
    ordering_fields = ["participant_role", "invited_at", "attendance_status"]

    def perform_create(self, serializer):
        if serializer.validated_data["meeting"].status != Meeting.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Participants can only be added to draft meetings.")
        super().perform_create(serializer)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        participant = self.get_object()
        response_status = request.data.get("invitation_status")
        if response_status not in MeetingParticipant.InvitationStatus.values:
            return Response({"invitation_status": ["Invalid response."]}, status=status.HTTP_400_BAD_REQUEST)
        participant.invitation_status = response_status
        participant.response_comment = request.data.get("comment", "")
        participant.responded_at = timezone.now()
        participant.save(update_fields=["invitation_status", "response_comment", "responded_at"])
        return Response(self.get_serializer(participant).data)

    @action(detail=True, methods=["post"])
    def mark_attendance(self, request, pk=None):
        participant = self.get_object()
        attendance = request.data.get("attendance_status")
        if attendance not in MeetingParticipant.AttendanceStatus.values or attendance == MeetingParticipant.AttendanceStatus.UNMARKED:
            return Response({"attendance_status": ["Invalid attendance status."]}, status=status.HTTP_400_BAD_REQUEST)
        participant.attendance_status = attendance
        participant.attendance_notes = request.data.get("notes", "")
        participant.marked_by = request.user
        participant.marked_at = timezone.now()
        if attendance in [MeetingParticipant.AttendanceStatus.PRESENT, MeetingParticipant.AttendanceStatus.LATE, MeetingParticipant.AttendanceStatus.REMOTE] and not participant.check_in_at:
            participant.check_in_at = timezone.now()
        participant.save(update_fields=["attendance_status", "attendance_notes", "marked_by", "marked_at", "check_in_at"])
        return Response(self.get_serializer(participant).data)

    @action(detail=True, methods=["post"])
    def acknowledge_minutes(self, request, pk=None):
        participant = self.get_object()
        if participant.meeting.status != Meeting.Status.FINALIZED:
            return Response({"detail": "Minutes can be acknowledged after finalization."}, status=status.HTTP_400_BAD_REQUEST)
        participant.minutes_acknowledged_at = timezone.now()
        participant.save(update_fields=["minutes_acknowledged_at"])
        return Response(self.get_serializer(participant).data)


@extend_schema(tags=["Meetings"])
class MeetingMinutesRevisionViewSet(MeetingBaseViewSet):
    queryset = MeetingMinutesRevision.objects.select_related("meeting", "created_by", "approved_by")
    serializer_class = MeetingMinutesRevisionSerializer
    search_fields = ["meeting__meeting_number", "meeting__title", "title", "content", "summary"]
    ordering_fields = ["created_at", "version"]

    @transaction.atomic
    def perform_create(self, serializer):
        meeting = serializer.validated_data["meeting"]
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        if meeting.status not in [Meeting.Status.HELD, Meeting.Status.MINUTES_DRAFT, Meeting.Status.CHANGES_REQUESTED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Minutes can only be created after the meeting is held.")
        if request_user := self.request.user:
            if request_user.profile.role != "admin" and meeting.secretary_id != request_user.id:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only the meeting secretary can draft minutes.")
        latest = meeting.minutes_revisions.select_for_update().order_by("-version").first()
        meeting.minutes_revisions.update(is_current=False)
        attendance = [{"name": item.display_name, "role": item.participant_role, "attendance": item.attendance_status} for item in meeting.participants.all()]
        agenda = [{"sequence": item.sequence, "title": item.title, "status": item.status, "notes": item.notes} for item in meeting.agenda_items.all()]
        revision = serializer.save(madrasa=self.get_madrasa(), version=(latest.version + 1 if latest else 1), is_current=True, status=MeetingMinutesRevision.Status.DRAFT, attendance_snapshot=attendance, agenda_snapshot=agenda, created_by=self.request.user)
        MeetingAuditEvent.objects.create(madrasa=self.get_madrasa(), meeting=meeting, action="minutes_revision_created", from_status=meeting.status, to_status=meeting.status, actor=self.request.user, metadata={"revision": revision.id, "version": revision.version})

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Minutes revisions are immutable; create a new revision.")

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Minutes revisions cannot be deleted.")


@extend_schema(tags=["Meetings and Decisions"])
class MeetingDecisionViewSet(MeetingBaseViewSet):
    queryset = MeetingDecision.objects.select_related("meeting", "agenda_item", "proposed_by", "approved_by")
    serializer_class = MeetingDecisionSerializer
    search_fields = ["decision_number", "title", "decision_text", "meeting__meeting_number", "meeting__title"]
    ordering_fields = ["decision_number", "effective_date", "status", "created_at"]

    def perform_create(self, serializer):
        meeting = serializer.validated_data["meeting"]
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        if meeting.status not in [Meeting.Status.HELD, Meeting.Status.MINUTES_DRAFT, Meeting.Status.CHANGES_REQUESTED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Decisions can only be recorded after the meeting is held.")
        next_number = meeting.decisions.count() + 1
        serializer.save(madrasa=self.get_madrasa(), decision_number=f"{meeting.meeting_number}-D{next_number:02d}", proposed_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.meeting.status in [Meeting.Status.FINALIZED, Meeting.Status.ARCHIVED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Finalized decisions are locked.")
        super().perform_update(serializer)


@extend_schema(tags=["Meetings and Decisions"])
class MeetingActionItemViewSet(MeetingBaseViewSet):
    queryset = MeetingActionItem.objects.select_related("meeting", "decision", "owner", "created_by")
    serializer_class = MeetingActionItemSerializer
    search_fields = ["title", "description", "meeting__meeting_number", "meeting__title", "owner__username", "owner__first_name"]
    ordering_fields = ["due_date", "priority", "status", "progress_percentage"]

    def get_queryset(self):
        queryset = super().get_queryset()
        for field in ["status", "owner", "meeting"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        if self.request.query_params.get("overdue") == "true":
            queryset = queryset.filter(due_date__lt=timezone.localdate()).exclude(status__in=[MeetingActionItem.Status.COMPLETED, MeetingActionItem.Status.CANCELLED])
        return queryset

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        status_value = serializer.validated_data.get("status", instance.status)
        progress = serializer.validated_data.get("progress_percentage", instance.progress_percentage)
        extra = {}
        if status_value == MeetingActionItem.Status.COMPLETED:
            extra = {"progress_percentage": 100, "completed_at": instance.completed_at or timezone.now()}
        elif progress == 100:
            extra = {"status": MeetingActionItem.Status.COMPLETED, "completed_at": instance.completed_at or timezone.now()}
        else:
            extra = {"completed_at": None}
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(**extra)


@extend_schema(tags=["Meetings"])
class MeetingAttachmentViewSet(MeetingBaseViewSet):
    queryset = MeetingAttachment.objects.select_related("meeting", "agenda_item", "uploaded_by")
    serializer_class = MeetingAttachmentSerializer

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        upload = serializer.validated_data["file"]
        serializer.save(madrasa=self.get_madrasa(), original_name=upload.name, uploaded_by=self.request.user)


class MeetingDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = Meeting.objects.none()

    def list(self, request):
        tenant = self.get_madrasa()
        now = timezone.now()
        meetings = Meeting.objects.filter(madrasa=tenant)
        actions = MeetingActionItem.objects.filter(madrasa=tenant)
        return Response({
            "total": meetings.count(),
            "upcoming": meetings.filter(status=Meeting.Status.SCHEDULED, scheduled_start__gte=now).count(),
            "pending_minutes": meetings.filter(status__in=[Meeting.Status.HELD, Meeting.Status.MINUTES_DRAFT, Meeting.Status.CHANGES_REQUESTED]).count(),
            "awaiting_approval": meetings.filter(status=Meeting.Status.PENDING_APPROVAL).count(),
            "finalized": meetings.filter(status=Meeting.Status.FINALIZED).count(),
            "open_actions": actions.exclude(status__in=[MeetingActionItem.Status.COMPLETED, MeetingActionItem.Status.CANCELLED]).count(),
            "overdue_actions": actions.filter(due_date__lt=timezone.localdate()).exclude(status__in=[MeetingActionItem.Status.COMPLETED, MeetingActionItem.Status.CANCELLED]).count(),
            "completion_rate": round(actions.filter(status=MeetingActionItem.Status.COMPLETED).count() / actions.count() * 100, 1) if actions.exists() else 0,
            "recent": MeetingListSerializer(meetings[:10], many=True).data,
            "my_actions": MeetingActionItemSerializer(actions.filter(owner=request.user).exclude(status__in=[MeetingActionItem.Status.COMPLETED, MeetingActionItem.Status.CANCELLED])[:10], many=True, context={"request": request}).data,
        })
