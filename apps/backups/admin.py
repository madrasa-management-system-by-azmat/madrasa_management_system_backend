from django.contrib import admin
from .models import BackupRun, BackupSchedule

admin.site.register(BackupSchedule)
admin.site.register(BackupRun)
