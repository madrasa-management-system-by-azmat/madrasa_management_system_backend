from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class TaskCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    color_key = models.CharField(max_length=30, default="primary")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_task_category_per_madrasa")]

    def __str__(self):
        return self.name


class TaskProject(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "منصوبہ بند"
        ACTIVE = "active", "جاری"
        ON_HOLD = "on_hold", "موقوف"
        COMPLETED = "completed", "مکمل"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_projects")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="task_projects_owned")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    starts_on = models.DateField(blank=True, null=True)
    due_on = models.DateField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="task_projects_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_on", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_task_project_per_madrasa")]


class TaskNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_number_sequences")
    year = models.PositiveSmallIntegerField()
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year"], name="unique_task_sequence_year")]


class AdministrativeTask(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        ASSIGNED = "assigned", "تفویض شدہ"
        IN_PROGRESS = "in_progress", "جاری"
        BLOCKED = "blocked", "رکا ہوا"
        PENDING_REVIEW = "pending_review", "جائزے کے لیے"
        CHANGES_REQUESTED = "changes_requested", "ترمیم مطلوب"
        COMPLETED = "completed", "مکمل"
        CANCELLED = "cancelled", "منسوخ"
        ARCHIVED = "archived", "محفوظ"

    class Priority(models.TextChoices):
        LOW = "low", "کم"
        NORMAL = "normal", "عام"
        HIGH = "high", "اہم"
        CRITICAL = "critical", "نہایت اہم"

    class Visibility(models.TextChoices):
        ASSIGNEES = "assignees", "ذمہ دار افراد"
        STAFF = "staff", "تمام عملہ"
        CONFIDENTIAL = "confidential", "خفیہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="administrative_tasks")
    task_number = models.CharField(max_length=50)
    sequence_year = models.PositiveSmallIntegerField()
    sequence_number = models.PositiveIntegerField()
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    category = models.ForeignKey(TaskCategory, on_delete=models.PROTECT, related_name="tasks")
    project = models.ForeignKey(TaskProject, on_delete=models.SET_NULL, blank=True, null=True, related_name="tasks")
    meeting_action = models.OneToOneField("meetings.MeetingActionItem", on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_task")
    parent = models.ForeignKey("self", on_delete=models.PROTECT, blank=True, null=True, related_name="subtasks")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.ASSIGNEES)
    starts_on = models.DateField(blank=True, null=True)
    due_at = models.DateTimeField(blank=True, null=True, db_index=True)
    estimated_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    requires_review = models.BooleanField(default=False)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_tasks_to_review")
    completion_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_tasks_verified")
    cancellation_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_tasks_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_tasks_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "-priority", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "task_number"], name="unique_admin_task_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "sequence_year", "sequence_number"], name="unique_admin_task_sequence"),
        ]

    @classmethod
    def issue_number(cls, madrasa, year=None):
        year = year or timezone.localdate().year
        with transaction.atomic():
            sequence, _ = TaskNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return year, value, f"TSK-{madrasa.id}-{year}-{value:06d}"

    def __str__(self):
        return f"{self.task_number} — {self.title}"


class TaskAssignment(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "مرکزی ذمہ دار"
        COLLABORATOR = "collaborator", "معاون"
        OBSERVER = "observer", "مبصر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_assignments")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.CASCADE, related_name="assignments")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="administrative_task_assignments")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="administrative_task_assignments_created")
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["role", "assigned_at"]
        constraints = [models.UniqueConstraint(fields=["task", "assignee"], name="unique_assignee_per_admin_task")]


class TaskChecklistItem(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_checklist_items")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.CASCADE, related_name="checklist_items")
    sequence = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=250)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="task_checklist_completed")
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["task", "sequence"], name="unique_task_checklist_sequence")]


class TaskDependency(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_dependencies")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.CASCADE, related_name="dependencies")
    depends_on = models.ForeignKey(AdministrativeTask, on_delete=models.PROTECT, related_name="dependents")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "depends_on"], name="unique_admin_task_dependency"),
            models.CheckConstraint(check=~models.Q(task=models.F("depends_on")), name="admin_task_not_self_dependent"),
        ]


class TaskComment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_comments")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.PROTECT, related_name="comments")
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="task_comments_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class TaskAttachment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_attachments")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(upload_to="tasks/attachments/")
    original_name = models.CharField(max_length=255)
    description = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="task_attachments_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class TaskRecurrence(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "روزانہ"
        WEEKLY = "weekly", "ہفتہ وار"
        MONTHLY = "monthly", "ماہانہ"
        YEARLY = "yearly", "سالانہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_recurrences")
    template_task = models.OneToOneField(AdministrativeTask, on_delete=models.CASCADE, related_name="recurrence")
    frequency = models.CharField(max_length=20, choices=Frequency.choices)
    interval = models.PositiveSmallIntegerField(default=1)
    next_run_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)


class TaskAuditEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="task_audit_events")
    task = models.ForeignKey(AdministrativeTask, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=60)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="task_audit_events")
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
