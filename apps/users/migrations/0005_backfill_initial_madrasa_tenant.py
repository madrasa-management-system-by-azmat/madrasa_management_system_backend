from django.db import migrations
from django.utils.text import slugify


def backfill_initial_tenant(apps, schema_editor):
    Madrasa = apps.get_model("users", "Madrasa")
    MadrasaProfile = apps.get_model("users", "MadrasaProfile")
    UserProfile = apps.get_model("users", "UserProfile")

    profile = MadrasaProfile.objects.order_by("id").first()
    name = (profile.name if profile and profile.name else "Default Madrasa")
    base_slug = slugify(name) or "default-madrasa"
    slug = base_slug
    suffix = 2
    while Madrasa.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    tenant, _ = Madrasa.objects.get_or_create(name=name, defaults={"slug": slug})

    if profile:
        profile.madrasa_id = tenant.id
        profile.save(update_fields=["madrasa"])

    UserProfile.objects.filter(madrasa__isnull=True).update(madrasa=tenant)

    for app_label, model_name in [
        ("students", "Department"), ("students", "AcademicClass"), ("students", "Halaqa"), ("students", "Student"), ("students", "StudentAttendance"),
        ("academics", "Subject"),
        ("staff", "Staff"), ("staff", "StaffAttendance"), ("staff", "HalaqaAssignment"),
        ("exams", "InternalExam"), ("exams", "InternalExamPaper"), ("exams", "InternalExamResult"), ("exams", "WafaqBoardRegistration"), ("exams", "WafaqResult"),
        ("finance", "Fund"), ("finance", "Donor"), ("finance", "Donation"), ("finance", "StudentFeeLog"), ("finance", "StudentMonthlyFee"), ("finance", "StudentFeePayment"), ("finance", "TeacherSalary"), ("finance", "StudentSponsorship"), ("finance", "Expense"),
        ("hifz", "HifzDailyLog"),
        ("hostel", "HostelWing"), ("hostel", "HostelRoom"), ("hostel", "HostelAllocation"), ("hostel", "GatePass"),
    ]:
        apps.get_model(app_label, model_name).objects.filter(madrasa__isnull=True).update(madrasa=tenant)


def reverse_backfill(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_madrasa_alter_userprofile_role_and_more"),
        ("students", "0005_academicclass_madrasa_department_madrasa_and_more"),
        ("academics", "0003_subject_madrasa"),
        ("staff", "0003_halaqaassignment_madrasa_staff_madrasa_and_more"),
        ("exams", "0008_internalexam_madrasa_internalexampaper_madrasa_and_more"),
        ("finance", "0005_donation_madrasa_donor_madrasa_expense_madrasa_and_more"),
        ("hifz", "0003_hifzdailylog_madrasa"),
        ("hostel", "0003_gatepass_madrasa_hostelallocation_madrasa_and_more"),
    ]

    operations = [migrations.RunPython(backfill_initial_tenant, reverse_backfill)]
