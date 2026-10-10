from django.conf import settings
from django.db import models
from django.utils import timezone


class Subject(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="subjects", null=True, blank=True)
    name = models.CharField(max_length=150)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.CASCADE, related_name="subjects")
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=40)

    class Meta:
        ordering = ["academic_class__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["academic_class", "name"], name="unique_subject_per_class")
        ]

    def __str__(self):
        return self.name


class ClassOffering(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "منصوبہ بند"
        ACTIVE = "active", "جاری"
        CLOSED = "closed", "مکمل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="class_offerings")
    academic_year = models.ForeignKey("students.AcademicYear", on_delete=models.PROTECT, related_name="class_offerings")
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.PROTECT, related_name="offerings")
    section = models.CharField(max_length=50, blank=True, default="")
    class_teacher = models.ForeignKey("staff.Staff", on_delete=models.SET_NULL, blank=True, null=True, related_name="class_offerings_led")
    assistant_teacher = models.ForeignKey("staff.Staff", on_delete=models.SET_NULL, blank=True, null=True, related_name="class_offerings_assisted")
    room = models.CharField(max_length=100, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["academic_year__starts_on", "academic_class__name", "section"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "academic_year", "academic_class", "section"], name="unique_class_offering_per_year_section")]


class CurriculumPlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        ACTIVE = "active", "جاری"
        COMPLETED = "completed", "مکمل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="curriculum_plans")
    class_offering = models.ForeignKey(ClassOffering, on_delete=models.CASCADE, related_name="curriculum_plans")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="curriculum_plans")
    teaching_assignment = models.ForeignKey("staff.TeachingAssignment", on_delete=models.SET_NULL, blank=True, null=True, related_name="curriculum_plans")
    title = models.CharField(max_length=200)
    planned_start = models.DateField()
    planned_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="curriculum_plans_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["class_offering", "subject"], name="unique_curriculum_subject_per_offering")]


class CurriculumBook(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="curriculum_books")
    plan = models.ForeignKey(CurriculumPlan, on_delete=models.CASCADE, related_name="books")
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=150, blank=True)
    publisher = models.CharField(max_length=150, blank=True)
    edition = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]


class CurriculumUnit(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "باقی"
        IN_PROGRESS = "in_progress", "جاری"
        COMPLETED = "completed", "مکمل"
        DELAYED = "delayed", "تاخیر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="curriculum_units")
    plan = models.ForeignKey(CurriculumPlan, on_delete=models.CASCADE, related_name="units")
    book = models.ForeignKey(CurriculumBook, on_delete=models.SET_NULL, blank=True, null=True, related_name="units")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, blank=True, null=True, related_name="children")
    title = models.CharField(max_length=250)
    sequence = models.PositiveIntegerField(default=1)
    planned_month = models.PositiveSmallIntegerField(blank=True, null=True)
    target_start = models.DateField(blank=True, null=True)
    target_end = models.DateField(blank=True, null=True)
    estimated_periods = models.PositiveSmallIntegerField(default=1)
    completion_percentage = models.PositiveSmallIntegerField(default=0)
    completed_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    delay_reason = models.CharField(max_length=250, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="curriculum_units_verified")
    verified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["sequence", "id"]


class TimetablePeriod(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, "پیر"
        TUESDAY = 2, "منگل"
        WEDNESDAY = 3, "بدھ"
        THURSDAY = 4, "جمعرات"
        FRIDAY = 5, "جمعہ"
        SATURDAY = 6, "ہفتہ"
        SUNDAY = 7, "اتوار"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="timetable_periods")
    academic_year = models.ForeignKey("students.AcademicYear", on_delete=models.CASCADE, related_name="timetable_periods")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    period_number = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=50, blank=True)
    starts_at = models.TimeField()
    ends_at = models.TimeField()

    class Meta:
        ordering = ["weekday", "period_number"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "academic_year", "weekday", "period_number"], name="unique_timetable_period")]


class TimetableEntry(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        PUBLISHED = "published", "جاری"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="timetable_entries")
    class_offering = models.ForeignKey(ClassOffering, on_delete=models.CASCADE, related_name="timetable_entries")
    period = models.ForeignKey(TimetablePeriod, on_delete=models.CASCADE, related_name="entries")
    teaching_assignment = models.ForeignKey("staff.TeachingAssignment", on_delete=models.PROTECT, related_name="timetable_entries")
    room = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="timetable_entries_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["period__weekday", "period__period_number"]
        constraints = [models.UniqueConstraint(fields=["class_offering", "period"], name="unique_class_timetable_period")]


class DailyLesson(models.Model):
    class DeliveryStatus(models.TextChoices):
        PLANNED = "planned", "منصوبہ"
        DELIVERED = "delivered", "پڑھایا گیا"
        PARTIAL = "partial", "جزوی"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="daily_lessons")
    class_offering = models.ForeignKey(ClassOffering, on_delete=models.PROTECT, related_name="daily_lessons")
    teaching_assignment = models.ForeignKey("staff.TeachingAssignment", on_delete=models.PROTECT, related_name="daily_lessons")
    timetable_entry = models.ForeignKey(TimetableEntry, on_delete=models.SET_NULL, blank=True, null=True, related_name="daily_lessons")
    lesson_date = models.DateField(default=timezone.localdate)
    portion_taught = models.TextField()
    homework = models.TextField(blank=True)
    lesson_objective = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    delivery_status = models.CharField(max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.DELIVERED)
    curriculum_units = models.ManyToManyField(CurriculumUnit, blank=True, related_name="lessons")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="daily_lessons_submitted")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="daily_lessons_verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-lesson_date", "-id"]


class LessonStudentAttention(models.Model):
    class AttentionType(models.TextChoices):
        WEAK = "weak", "کمزور"
        REMEDIAL = "remedial", "خصوصی توجہ"
        ABSENT = "absent", "غیر حاضر"
        EXCEPTIONAL = "exceptional", "نمایاں"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="lesson_student_attention")
    lesson = models.ForeignKey(DailyLesson, on_delete=models.CASCADE, related_name="student_attention")
    enrollment = models.ForeignKey("students.StudentEnrollment", on_delete=models.PROTECT, related_name="lesson_attention")
    attention_type = models.CharField(max_length=20, choices=AttentionType.choices)
    observation = models.TextField(blank=True)
    recommended_action = models.TextField(blank=True)
    follow_up_date = models.DateField(blank=True, null=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
