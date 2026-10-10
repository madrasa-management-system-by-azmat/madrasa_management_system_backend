from django.contrib import admin

from .models import AdministrativeTask, TaskAssignment, TaskAttachment, TaskAuditEvent, TaskCategory, TaskChecklistItem, TaskComment, TaskDependency, TaskNumberSequence, TaskProject, TaskRecurrence

admin.site.register(TaskCategory)
admin.site.register(TaskProject)
admin.site.register(TaskNumberSequence)
admin.site.register(AdministrativeTask)
admin.site.register(TaskAssignment)
admin.site.register(TaskChecklistItem)
admin.site.register(TaskDependency)
admin.site.register(TaskComment)
admin.site.register(TaskAttachment)
admin.site.register(TaskRecurrence)
admin.site.register(TaskAuditEvent)
