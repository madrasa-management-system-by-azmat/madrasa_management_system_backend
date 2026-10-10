import hashlib
import json
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditEvent(models.Model):
    class Category(models.TextChoices):
        DATA = "data", "Data"
        WORKFLOW = "workflow", "Workflow"
        AUTH = "auth", "Authentication"
        SECURITY = "security", "Security"
        BACKUP = "backup", "Backup"
        RESTORE = "restore", "Restore"
        ARCHIVE = "archive", "Archive"
        ACCESS = "access", "Access"
        SYSTEM = "system", "System"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.PROTECT, blank=True, null=True, related_name="central_audit_events")
    request_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    action = models.CharField(max_length=60, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="central_audit_events")
    actor_label = models.CharField(max_length=200, blank=True)
    entity_type = models.CharField(max_length=150, blank=True, db_index=True)
    entity_id = models.CharField(max_length=100, blank=True, db_index=True)
    entity_label = models.CharField(max_length=300, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    previous_hash = models.CharField(max_length=64, blank=True)
    event_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["madrasa", "created_at"]), models.Index(fields=["madrasa", "category", "action"])]

    @staticmethod
    def compute_hash(payload):
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit events cannot be deleted.")


class ArchivePolicy(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="archive_policies")
    name = models.CharField(max_length=150)
    entity_type = models.CharField(max_length=150)
    age_days = models.PositiveIntegerField(default=365)
    terminal_statuses = models.JSONField(default=list)
    retention_years = models.PositiveSmallIntegerField(default=7)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="archive_policies_created")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "entity_type"], name="unique_archive_policy_entity")]


class ArchiveBatch(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        RESTORED = "restored", "Restored"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.PROTECT, related_name="archive_batches")
    batch_number = models.CharField(max_length=60, unique=True)
    policy = models.ForeignKey(ArchivePolicy, on_delete=models.SET_NULL, blank=True, null=True, related_name="batches")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    criteria = models.JSONField(default=dict)
    record_count = models.PositiveIntegerField(default=0)
    manifest_hash = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="archive_batches_created")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    restored_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="archive_batches_restored")
    restored_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]


class ArchivedRecord(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.PROTECT, related_name="archived_records")
    batch = models.ForeignKey(ArchiveBatch, on_delete=models.PROTECT, related_name="records")
    entity_type = models.CharField(max_length=150, db_index=True)
    entity_id = models.CharField(max_length=100, db_index=True)
    entity_label = models.CharField(max_length=300)
    snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    source_status = models.CharField(max_length=50, blank=True)
    source_status_field = models.CharField(max_length=50, blank=True)
    archived_at = models.DateTimeField(default=timezone.now)
    restored_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "entity_type", "entity_id"], name="unique_archived_batch_record")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Archived snapshots are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Archived snapshots cannot be deleted.")


class LegalHold(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.PROTECT, related_name="legal_holds")
    name = models.CharField(max_length=200)
    reason = models.TextField()
    entity_type = models.CharField(max_length=150, blank=True)
    entity_id = models.CharField(max_length=100, blank=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="legal_holds_created")
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="legal_holds_released")
    released_at = models.DateTimeField(blank=True, null=True)
