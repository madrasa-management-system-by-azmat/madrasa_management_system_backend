from django.contrib import admin

from .models import (
	HalaqaAssignment,
	PerformanceGoal,
	PerformanceMetric,
	PerformanceReview,
	Staff,
	StaffAttendance,
	StaffContribution,
	SyllabusPlan,
	SyllabusProgressEntry,
	TeachingAssignment,
)

admin.site.register(Staff)
admin.site.register(StaffAttendance)
admin.site.register(HalaqaAssignment)
admin.site.register(TeachingAssignment)
admin.site.register(SyllabusPlan)
admin.site.register(SyllabusProgressEntry)
admin.site.register(StaffContribution)
admin.site.register(PerformanceReview)
admin.site.register(PerformanceMetric)
admin.site.register(PerformanceGoal)
