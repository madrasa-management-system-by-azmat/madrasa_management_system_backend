from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.backups.models import BackupRun, BackupSchedule
from apps.backups.services import create_and_execute_backup


class Command(BaseCommand):
    help = "Create every tenant backup whose persisted schedule is due."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)

    def handle(self, *args, **options):
        now = timezone.now()
        schedules = BackupSchedule.objects.filter(is_active=True, next_run_at__lte=now, madrasa__is_active=True).select_related("madrasa").order_by("next_run_at")[: options["limit"]]
        completed = failed = 0
        for schedule in schedules:
            due_at = schedule.next_run_at
            run = create_and_execute_backup(madrasa=schedule.madrasa, trigger=BackupRun.Trigger.SCHEDULED, schedule=schedule, scheduled_for=due_at)
            if run.status == BackupRun.Status.COMPLETED:
                completed += 1
                self.stdout.write(self.style.SUCCESS(f"Completed {schedule.madrasa.slug}: {run.filename}"))
            else:
                failed += 1
                self.stderr.write(f"Failed {schedule.madrasa.slug}: {run.error_message}")
        self.stdout.write(f"Processed {len(schedules)} schedule(s): {completed} completed, {failed} failed.")
