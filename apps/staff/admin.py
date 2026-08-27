from django.contrib import admin

from .models import HalaqaAssignment, Staff, StaffAttendance

admin.site.register(Staff)
admin.site.register(StaffAttendance)
admin.site.register(HalaqaAssignment)
