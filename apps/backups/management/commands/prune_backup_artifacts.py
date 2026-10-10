from django.core.management.base import BaseCommand
from apps.backups.models import BackupSchedule
from apps.backups.services import prune_backups


class Command(BaseCommand):
    help = "Delete expired or excess private backup artifacts according to tenant retention settings."

    def handle(self, *args, **options):
        removed = 0
        for schedule in BackupSchedule.objects.select_related("madrasa"):
            removed += prune_backups(schedule.madrasa, schedule)
        self.stdout.write(self.style.SUCCESS(f"Removed {removed} backup artifact(s)."))
