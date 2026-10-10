from django.conf import settings
from django.db import models
from django.utils import timezone


class Staff(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="staff_members", null=True, blank=True)
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Teacher"
        ACCOUNTANT = "accountant", "Accountant"
        HOSTEL_WARDEN = "hostel_warden", "Hostel Warden"
        STAFF = "staff", "Staff"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="staff_profile",
    )
    full_name = models.CharField(max_length=200)
    photo = models.ImageField(upload_to="staff/photos/", blank=True, null=True)
    cnic = models.CharField(max_length=20, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=20)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.STAFF)
    hire_date = models.DateField()
    is_residential = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class StaffAttendance(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="staff_attendance", null=True, blank=True)
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LEAVE = "leave", "Leave"
        LATE = "late", "Late"
        HALF_DAY = "half_day", "Half day"
        OFFICIAL_DUTY = "official_duty", "Official duty"

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices)
    check_in = models.TimeField(blank=True, null=True)
    check_out = models.TimeField(blank=True, null=True)
    expected_check_in = models.TimeField(blank=True, null=True)
    late_minutes = models.PositiveSmallIntegerField(default=0)
    remarks = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="staff_attendance_recorded")

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["staff", "date"], name="unique_staff_attendance_per_day")
        ]


class HalaqaAssignment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="halaqa_assignments", null=True, blank=True)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="halaqa_assignments")
    halaqa = models.ForeignKey("students.Halaqa", on_delete=models.CASCADE, related_name="staff_assignments")
    assigned_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "halaqa"], name="unique_staff_halaqa_assignment")
        ]


class TeachingAssignment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="teaching_assignments")
    teacher = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="teaching_assignments")
    academic_year = models.ForeignKey("students.AcademicYear", on_delete=models.PROTECT, related_name="teaching_assignments")
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.PROTECT, related_name="teaching_assignments")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="teaching_assignments")
    weekly_periods = models.PositiveSmallIntegerField(default=1)
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="teaching_assignments_created")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["teacher__full_name", "academic_class__name", "subject__name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "teacher", "academic_year", "academic_class", "subject"], name="unique_teacher_subject_assignment")]


class SyllabusPlan(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="syllabus_plans")
    assignment = models.OneToOneField(TeachingAssignment, on_delete=models.CASCADE, related_name="syllabus_plan")
    title = models.CharField(max_length=200)
    total_units = models.PositiveIntegerField(default=1)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)


class SyllabusProgressEntry(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="syllabus_progress_entries")
    plan = models.ForeignKey(SyllabusPlan, on_delete=models.CASCADE, related_name="progress_entries")
    date = models.DateField(default=timezone.localdate)
    topic = models.CharField(max_length=250)
    units_completed = models.PositiveIntegerField(default=1)
    remarks = models.TextField(blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="syllabus_progress_submitted")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="syllabus_progress_verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class StaffContribution(models.Model):
    class Category(models.TextChoices):
        MEETING = "meeting", "Meeting"
        TRAINING = "training", "Training"
        ADMINISTRATIVE = "administrative", "Administrative duty"
        EXAM = "exam", "Exam duty"

    class ParticipationStatus(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        ATTENDED = "attended", "Attended"
        COMPLETED = "completed", "Completed"
        MISSED = "missed", "Missed"
        EXCUSED = "excused", "Excused"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="staff_contributions")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="contributions")
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=250)
    scheduled_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    expected_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    participation_status = models.CharField(max_length=20, choices=ParticipationStatus.choices, default=ParticipationStatus.ASSIGNED)
    responsibility = models.TextField(blank=True)
    remarks = models.TextField(blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="staff_contributions_assigned")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="staff_contributions_verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PerformanceReview(models.Model):
    class ReviewType(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="performance_reviews")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="performance_reviews")
    review_type = models.CharField(max_length=20, choices=ReviewType.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rating = models.CharField(max_length=50, blank=True)
    manager_comments = models.TextField(blank=True)
    teacher_comments = models.TextField(blank=True)
    metrics_snapshot = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="performance_reviews_reviewed")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="performance_reviews_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "staff__full_name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "staff", "review_type", "period_start", "period_end"], name="unique_staff_performance_review_period")]


class PerformanceMetric(models.Model):
    review = models.ForeignKey(PerformanceReview, on_delete=models.CASCADE, related_name="metrics")
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=150)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    raw_value = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    normalized_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    weighted_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    source_count = models.PositiveIntegerField(default=0)
    adjustment = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    adjustment_reason = models.CharField(max_length=250, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["review", "code"], name="unique_performance_metric_code")]


class PerformanceGoal(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="performance_goals")
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="performance_goals")
    review = models.ForeignKey(PerformanceReview, on_delete=models.SET_NULL, blank=True, null=True, related_name="goals")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    progress_percentage = models.PositiveSmallIntegerField(default=0)
    teacher_update = models.TextField(blank=True)
    reviewer_remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="performance_goals_created")
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "target_date"]
