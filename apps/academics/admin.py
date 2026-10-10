from django.contrib import admin

from .models import (
	ClassOffering,
	CurriculumBook,
	CurriculumPlan,
	CurriculumUnit,
	DailyLesson,
	LessonStudentAttention,
	Subject,
	TimetableEntry,
	TimetablePeriod,
)

admin.site.register(Subject)
admin.site.register(ClassOffering)
admin.site.register(CurriculumPlan)
admin.site.register(CurriculumBook)
admin.site.register(CurriculumUnit)
admin.site.register(TimetablePeriod)
admin.site.register(TimetableEntry)
admin.site.register(DailyLesson)
admin.site.register(LessonStudentAttention)
