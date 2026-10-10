import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class BackupSchedule(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    madrasa = models.OneToOneField("users.Madrasa", on_delete=models.CASCADE, related_name="backup_schedule")
    is_active = models.BooleanField(default=False)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.DAILY)
    time_of_day = models.TimeField(default="02:00")
    weekday = models.PositiveSmallIntegerField(default=0)
    day_of_month = models.PositiveSmallIntegerField(default=1)
    timezone = models.CharField(max_length=50, default="Asia/Karachi")
    retention_count = models.PositiveSmallIntegerField(default=14, validators=[MinValueValidator(1)])
    retention_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1)])
    include_media = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="backup_schedules_created")
    updated_at = models.DateTimeField(auto_now=True)


class BackupRun(models.Model):
    class Trigger(models.TextChoices):
        MANUAL = "manual", "Manual"
        SCHEDULED = "scheduled", "Scheduled"
        COMMAND = "command", "Command"
        PRE_RESTORE = "pre_restore", "Pre-restore"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.PROTECT, related_name="backup_runs")
    schedule = models.ForeignKey(BackupSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs")
    trigger = models.CharField(max_length=20, choices=Trigger.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="backup_runs_requested")
    filename = models.CharField(max_length=255, blank=True)
    storage_path = models.CharField(max_length=500, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    record_count = models.PositiveIntegerField(default=0)
    media_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["madrasa", "status", "created_at"])]
