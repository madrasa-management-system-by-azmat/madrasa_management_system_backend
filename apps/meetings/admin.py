from django.contrib import admin

from .models import Meeting, MeetingActionItem, MeetingAgendaItem, MeetingAttachment, MeetingAuditEvent, MeetingDecision, MeetingMinutesRevision, MeetingNumberSequence, MeetingParticipant, MeetingType

admin.site.register(MeetingType)
admin.site.register(MeetingNumberSequence)
admin.site.register(Meeting)
admin.site.register(MeetingAgendaItem)
admin.site.register(MeetingParticipant)
admin.site.register(MeetingMinutesRevision)
admin.site.register(MeetingDecision)
admin.site.register(MeetingActionItem)
admin.site.register(MeetingAttachment)
admin.site.register(MeetingAuditEvent)
