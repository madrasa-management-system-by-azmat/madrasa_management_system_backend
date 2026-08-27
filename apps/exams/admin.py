from django.contrib import admin

from .models import InternalExam, InternalExamResult, WafaqBoardRegistration, WafaqResult

admin.site.register(InternalExam)
admin.site.register(InternalExamResult)
admin.site.register(WafaqBoardRegistration)
admin.site.register(WafaqResult)
