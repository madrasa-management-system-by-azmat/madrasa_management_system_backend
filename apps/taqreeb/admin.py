from django.contrib import admin

from .models import DutyAssignment, DutyCategory, GuestInvitation, Taqreeb


@admin.register(Taqreeb)
class TaqreebAdmin(admin.ModelAdmin):
    list_display = ("title", "madrasa", "event_type", "event_date", "status", "venue")
    list_filter = ("status", "event_type", "event_date")
    search_fields = ("title", "venue", "chief_guest")


@admin.register(DutyCategory)
class DutyCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "madrasa", "code", "color", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "code")


@admin.register(DutyAssignment)
class DutyAssignmentAdmin(admin.ModelAdmin):
    list_display = ("card_number", "duty_title", "taqreeb", "assignee_type", "status")
    list_filter = ("status", "assignee_type", "taqreeb")
    search_fields = ("card_number", "duty_title", "student__full_name", "staff__full_name")


@admin.register(GuestInvitation)
class GuestInvitationAdmin(admin.ModelAdmin):
    list_display = ("invitation_number", "guest_name", "taqreeb", "phone", "status", "is_special_guest")
    list_filter = ("status", "is_special_guest", "taqreeb")
    search_fields = ("invitation_number", "guest_name", "phone", "organization")

