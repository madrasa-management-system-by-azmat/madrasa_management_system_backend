from django.contrib import admin

from .models import AnnualResult, ExamAttendance, ExamDuty, ExamResultChange, InternalExam, InternalExamResult, WafaqBoardRegistration, WafaqResult

admin.site.register(InternalExam)
admin.site.register(InternalExamResult)
admin.site.register(WafaqBoardRegistration)
admin.site.register(WafaqResult)
admin.site.register(ExamDuty)
admin.site.register(ExamAttendance)
admin.site.register(ExamResultChange)
admin.site.register(AnnualResult)
