from django.contrib import admin

from .models import InstitutionCalendarDay, LeaveAttachment, LeaveAuditEvent, LeaveBalance, LeavePolicy, LeavePolicyRule, LeaveRequest, LeaveRequestDay, LeaveSubstitution, LeaveType

admin.site.register(InstitutionCalendarDay)
admin.site.register(LeaveType)
admin.site.register(LeavePolicy)
admin.site.register(LeavePolicyRule)
admin.site.register(LeaveBalance)
admin.site.register(LeaveRequest)
admin.site.register(LeaveRequestDay)
admin.site.register(LeaveSubstitution)
admin.site.register(LeaveAttachment)
admin.site.register(LeaveAuditEvent)
