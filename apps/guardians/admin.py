from django.contrib import admin

from .models import GuardianAnnouncement, GuardianAnnouncementRead, GuardianConsent, GuardianInvitation, GuardianNotificationPreference, GuardianProfile, GuardianStudentLink, ParentMeetingBooking, ParentMeetingSlot

admin.site.register(GuardianProfile)
admin.site.register(GuardianStudentLink)
admin.site.register(GuardianInvitation)
admin.site.register(GuardianConsent)
admin.site.register(GuardianNotificationPreference)
admin.site.register(ParentMeetingSlot)
admin.site.register(ParentMeetingBooking)
admin.site.register(GuardianAnnouncement)
admin.site.register(GuardianAnnouncementRead)
