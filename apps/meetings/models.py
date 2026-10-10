from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class MeetingType(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_types")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    default_duration_minutes = models.PositiveSmallIntegerField(default=60)
    default_quorum = models.PositiveSmallIntegerField(default=1)
    requires_approval = models.BooleanField(default=True)
    is_confidential = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_meeting_type_per_madrasa")]

    def __str__(self):
        return self.name


class MeetingNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_number_sequences")
    year = models.PositiveSmallIntegerField()
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year"], name="unique_meeting_sequence_year")]


class Meeting(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        SCHEDULED = "scheduled", "مقرر"
        HELD = "held", "منعقد"
        MINUTES_DRAFT = "minutes_draft", "روداد کا مسودہ"
        PENDING_APPROVAL = "pending_approval", "منظوری کے لیے"
        CHANGES_REQUESTED = "changes_requested", "ترمیم مطلوب"
        FINALIZED = "finalized", "حتمی"
        CANCELLED = "cancelled", "منسوخ"
        ARCHIVED = "archived", "محفوظ"

    class Visibility(models.TextChoices):
        PARTICIPANTS = "participants", "شرکاء"
        STAFF = "staff", "تمام عملہ"
        CONFIDENTIAL = "confidential", "خفیہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meetings")
    meeting_number = models.CharField(max_length=50)
    sequence_year = models.PositiveSmallIntegerField()
    sequence_number = models.PositiveIntegerField()
    meeting_type = models.ForeignKey(MeetingType, on_delete=models.PROTECT, related_name="meetings")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.PARTICIPANTS)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(blank=True, null=True)
    actual_end = models.DateTimeField(blank=True, null=True)
    venue = models.CharField(max_length=200, blank=True)
    online_url = models.URLField(blank=True)
    chairperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_chaired")
    secretary = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_secretaried")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_to_approve")
    quorum_required = models.PositiveSmallIntegerField(default=1)
    quorum_met = models.BooleanField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True)
    finalized_at = models.DateTimeField(blank=True, null=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_finalized")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meetings_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_start", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "meeting_number"], name="unique_meeting_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "sequence_year", "sequence_number"], name="unique_meeting_sequence_number"),
        ]

    @classmethod
    def issue_number(cls, madrasa, year=None):
        year = year or timezone.localdate().year
        with transaction.atomic():
            sequence, _ = MeetingNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return year, value, f"MTG-{madrasa.id}-{year}-{value:05d}"

    def __str__(self):
        return f"{self.meeting_number} — {self.title}"


class MeetingAgendaItem(models.Model):
    class ItemType(models.TextChoices):
        INFORMATION = "information", "اطلاع"
        DISCUSSION = "discussion", "بحث"
        DECISION = "decision", "فیصلہ"
        REPORT = "report", "رپورٹ"

    class Status(models.TextChoices):
        PENDING = "pending", "زیر انتظار"
        DISCUSSED = "discussed", "زیر بحث"
        DEFERRED = "deferred", "مؤخر"
        COMPLETED = "completed", "مکمل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_agenda_items")
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="agenda_items")
    sequence = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    presenter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_agenda_presentations")
    allocated_minutes = models.PositiveSmallIntegerField(default=10)
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.DISCUSSION)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["meeting", "sequence"], name="unique_agenda_sequence_per_meeting")]


class MeetingParticipant(models.Model):
    class ParticipantRole(models.TextChoices):
        CHAIR = "chair", "صدر"
        SECRETARY = "secretary", "سیکریٹری"
        APPROVER = "approver", "منظور کنندہ"
        MEMBER = "member", "رکن"
        PRESENTER = "presenter", "پیش کنندہ"
        OBSERVER = "observer", "مبصر"

    class InvitationStatus(models.TextChoices):
        PENDING = "pending", "منتظر"
        ACCEPTED = "accepted", "منظور"
        DECLINED = "declined", "نامنظور"
        TENTATIVE = "tentative", "غیر یقینی"

    class AttendanceStatus(models.TextChoices):
        UNMARKED = "unmarked", "غیر درج"
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غیر حاضر"
        LATE = "late", "تاخیر"
        EXCUSED = "excused", "معذور"
        REMOTE = "remote", "آن لائن"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_participants")
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True, related_name="meeting_participations")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="meeting_participations")
    external_name = models.CharField(max_length=200, blank=True)
    external_email = models.EmailField(blank=True)
    participant_role = models.CharField(max_length=20, choices=ParticipantRole.choices, default=ParticipantRole.MEMBER)
    invitation_status = models.CharField(max_length=20, choices=InvitationStatus.choices, default=InvitationStatus.PENDING)
    attendance_status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.UNMARKED)
    response_comment = models.TextField(blank=True)
    attendance_notes = models.TextField(blank=True)
    invited_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(blank=True, null=True)
    check_in_at = models.DateTimeField(blank=True, null=True)
    check_out_at = models.DateTimeField(blank=True, null=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_attendance_marked")
    marked_at = models.DateTimeField(blank=True, null=True)
    minutes_acknowledged_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["participant_role", "id"]
        constraints = [
            models.UniqueConstraint(fields=["meeting", "user"], condition=models.Q(user__isnull=False), name="unique_meeting_user_participant"),
            models.UniqueConstraint(fields=["meeting", "staff"], condition=models.Q(staff__isnull=False), name="unique_meeting_staff_participant"),
        ]

    @property
    def display_name(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.username
        if self.staff_id:
            return self.staff.full_name
        return self.external_name


class MeetingMinutesRevision(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        SUBMITTED = "submitted", "جمع شدہ"
        CHANGES_REQUESTED = "changes_requested", "ترمیم مطلوب"
        APPROVED = "approved", "منظور"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_minutes_revisions")
    meeting = models.ForeignKey(Meeting, on_delete=models.PROTECT, related_name="minutes_revisions")
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=250)
    content = models.TextField()
    summary = models.TextField(blank=True)
    discussion_notes = models.TextField(blank=True)
    attendance_snapshot = models.JSONField(default=list, blank=True)
    agenda_snapshot = models.JSONField(default=list, blank=True)
    based_on = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="derived_revisions")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_minutes_created")
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_minutes_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    approval_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(fields=["meeting", "version"], name="unique_meeting_minutes_version"),
            models.UniqueConstraint(fields=["meeting"], condition=models.Q(is_current=True), name="one_current_minutes_revision"),
        ]


class MeetingDecision(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "تجویز"
        APPROVED = "approved", "منظور"
        REJECTED = "rejected", "نامنظور"
        SUPERSEDED = "superseded", "منسوخ شدہ"
        WITHDRAWN = "withdrawn", "واپس"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_decisions")
    meeting = models.ForeignKey(Meeting, on_delete=models.PROTECT, related_name="decisions")
    agenda_item = models.ForeignKey(MeetingAgendaItem, on_delete=models.SET_NULL, blank=True, null=True, related_name="decisions")
    decision_number = models.CharField(max_length=60)
    title = models.CharField(max_length=250)
    decision_text = models.TextField()
    rationale = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)
    effective_date = models.DateField(blank=True, null=True)
    is_confidential = models.BooleanField(default=False)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_decisions_proposed")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_decisions_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["decision_number"]
        constraints = [models.UniqueConstraint(fields=["meeting", "decision_number"], name="unique_decision_number_per_meeting")]


class MeetingActionItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "زیر انتظار"
        IN_PROGRESS = "in_progress", "جاری"
        COMPLETED = "completed", "مکمل"
        BLOCKED = "blocked", "رکا ہوا"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_action_items")
    meeting = models.ForeignKey(Meeting, on_delete=models.PROTECT, related_name="action_items")
    decision = models.ForeignKey(MeetingDecision, on_delete=models.SET_NULL, blank=True, null=True, related_name="action_items")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="meeting_actions_owned")
    due_date = models.DateField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=[("normal", "Normal"), ("high", "High"), ("critical", "Critical")], default="normal")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    completion_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_actions_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "-priority", "id"]


class MeetingAttachment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_attachments")
    meeting = models.ForeignKey(Meeting, on_delete=models.PROTECT, related_name="attachments")
    agenda_item = models.ForeignKey(MeetingAgendaItem, on_delete=models.SET_NULL, blank=True, null=True, related_name="attachments")
    file = models.FileField(upload_to="meetings/attachments/")
    original_name = models.CharField(max_length=255)
    description = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_attachments_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class MeetingAuditEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="meeting_audit_events")
    meeting = models.ForeignKey(Meeting, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=60)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="meeting_audit_events")
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
