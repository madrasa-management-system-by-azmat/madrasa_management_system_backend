from django.contrib import admin

from .models import AcademicClass, Department, Halaqa, Student


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
    ]
    list_filter = ["status", "gender", "residential_status", "current_class"]
    search_fields = ["registration_number", "full_name", "guardian_name", "phone"]
    readonly_fields = ["registration_number", "created_at", "updated_at"]
