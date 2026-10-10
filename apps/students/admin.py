from django.contrib import admin

from .models import (
    AcademicClass,
    AcademicYear,
    AdmissionApplication,
    AdmissionDecision,
    AdmissionInterview,
    AdmissionTest,
    AlumniProfile,
    Department,
    GraduationRecord,
    Halaqa,
    PromotionDecision,
    Student,
    StudentAttendance,
    StudentEnrollment,
    StudentLifecycleEvent,
    RollNumberChange,
    AttendanceAlert,
    AttendanceAlertRule,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(AcademicClass)
class AcademicClassAdmin(admin.ModelAdmin):
    list_display = ["name", "department"]
    list_filter = ["department"]
    search_fields = ["name"]


@admin.register(Halaqa)
class HalaqaAdmin(admin.ModelAdmin):
    list_display = ["name", "ustad_name"]
    search_fields = ["name", "ustad_name"]


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "registration_number",
        "full_name",
        "current_class",
        "current_halaqa",
        "status",
        "lifecycle_status",
    ]
    list_filter = ["status", "lifecycle_status", "gender", "residential_status", "current_class"]
    search_fields = ["registration_number", "full_name", "guardian_name", "phone"]
    readonly_fields = ["registration_number", "created_at", "updated_at"]


admin.site.register(AcademicYear)
admin.site.register(AdmissionApplication)
admin.site.register(AdmissionInterview)
admin.site.register(AdmissionTest)
admin.site.register(AdmissionDecision)
admin.site.register(StudentEnrollment)
admin.site.register(StudentLifecycleEvent)
admin.site.register(RollNumberChange)
admin.site.register(AttendanceAlertRule)
admin.site.register(AttendanceAlert)
admin.site.register(StudentAttendance)
admin.site.register(PromotionDecision)
admin.site.register(GraduationRecord)
admin.site.register(AlumniProfile)
