import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auditlog.services import audit_event
from apps.users.backup import create_backup

from .models import BackupRun, BackupSchedule


def backup_root():
    root = Path(getattr(settings, "BACKUP_ROOT", settings.BASE_DIR / "private" / "backups")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def calculate_next_run(schedule, after=None):
    tz = ZoneInfo(schedule.timezone)
    local = (after or timezone.now()).astimezone(tz)
    candidate = datetime.combine(local.date(), schedule.time_of_day, tzinfo=tz)
    if schedule.frequency == BackupSchedule.Frequency.DAILY:
        if candidate <= local:
            candidate += timedelta(days=1)
    elif schedule.frequency == BackupSchedule.Frequency.WEEKLY:
        candidate += timedelta(days=(schedule.weekday - candidate.weekday()) % 7)
        if candidate <= local:
            candidate += timedelta(days=7)
    else:
        day = min(schedule.day_of_month, 28)
        candidate = candidate.replace(day=day)
        if candidate <= local:
            year, month = candidate.year, candidate.month + 1
            if month == 13:
                year, month = year + 1, 1
            candidate = candidate.replace(year=year, month=month, day=day)
    return candidate.astimezone(ZoneInfo("UTC"))


def save_schedule(schedule):
    schedule.next_run_at = calculate_next_run(schedule) if schedule.is_active else None
    schedule.save()
    return schedule


def prune_backups(madrasa, schedule=None):
    schedule = schedule or getattr(madrasa, "backup_schedule", None)
    if not schedule:
        return 0
    completed = list(BackupRun.objects.filter(madrasa=madrasa, status=BackupRun.Status.COMPLETED).order_by("-completed_at"))
    now = timezone.now()
    removed = 0
    for index, run in enumerate(completed):
        expired = run.expires_at and run.expires_at <= now
        over_count = index >= schedule.retention_count
        if not expired and not over_count:
            continue
        path = Path(run.storage_path)
        if path.is_file():
            path.unlink()
        run.status = BackupRun.Status.DELETED
        run.storage_path = ""
        run.save(update_fields=["status", "storage_path"])
        audit_event(category="backup", action="backup_retention_deleted", madrasa=madrasa, entity=run)
        removed += 1
    return removed


@transaction.atomic
def claim_run(run_id):
    run = BackupRun.objects.select_for_update().get(pk=run_id)
    if run.status != BackupRun.Status.PENDING:
        return None
    if BackupRun.objects.filter(madrasa=run.madrasa, status=BackupRun.Status.RUNNING).exclude(pk=run.pk).exists():
        run.status = BackupRun.Status.SKIPPED
        run.error_message = "Another backup is already running."
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        return None
    run.status = BackupRun.Status.RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    return run


def execute_backup(run_id):
    run = claim_run(run_id)
    if not run:
        return BackupRun.objects.get(pk=run_id)
    audit_event(category="backup", action="backup_started", madrasa=run.madrasa, actor=run.requested_by, entity=run, metadata={"trigger": run.trigger})
    try:
        output = create_backup(run.madrasa, include_media=run.schedule.include_media if run.schedule else True)
        content = output.getvalue()
        tenant_dir = backup_root() / str(run.madrasa_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{run.madrasa.slug}-{timezone.now():%Y%m%d-%H%M%S}-{run.id}.zip"
        temp_path = tenant_dir / f".{filename}.tmp"
        final_path = tenant_dir / filename
        temp_path.write_bytes(content)
        os.replace(temp_path, final_path)
        digest = hashlib.sha256(content).hexdigest()
        run.status = BackupRun.Status.COMPLETED
        run.filename = filename
        run.storage_path = str(final_path)
        run.size_bytes = len(content)
        run.sha256 = digest
        run.completed_at = timezone.now()
        run.expires_at = run.completed_at + timedelta(days=(run.schedule.retention_days if run.schedule else 30))
        run.save(update_fields=["status", "filename", "storage_path", "size_bytes", "sha256", "completed_at", "expires_at"])
        if run.schedule:
            run.schedule.last_run_at = run.completed_at
            run.schedule.last_success_at = run.completed_at
            run.schedule.next_run_at = calculate_next_run(run.schedule, run.scheduled_for or run.completed_at) if run.schedule.is_active else None
            run.schedule.save(update_fields=["last_run_at", "last_success_at", "next_run_at"])
        prune_backups(run.madrasa, run.schedule)
        audit_event(category="backup", action="backup_completed", madrasa=run.madrasa, actor=run.requested_by, entity=run, metadata={"size_bytes": run.size_bytes, "sha256": digest})
    except Exception as error:
        run.status = BackupRun.Status.FAILED
        run.error_message = str(error)[:2000]
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        if run.schedule:
            run.schedule.last_run_at = run.completed_at
            run.schedule.next_run_at = calculate_next_run(run.schedule, run.scheduled_for or run.completed_at) if run.schedule.is_active else None
            run.schedule.save(update_fields=["last_run_at", "next_run_at"])
        audit_event(category="backup", action="backup_failed", madrasa=run.madrasa, actor=run.requested_by, entity=run, metadata={"error": run.error_message})
    return run


def create_and_execute_backup(*, madrasa, trigger, requested_by=None, schedule=None, scheduled_for=None):
    run = BackupRun.objects.create(madrasa=madrasa, schedule=schedule, trigger=trigger, requested_by=requested_by, scheduled_for=scheduled_for)
    return execute_backup(run.pk)
