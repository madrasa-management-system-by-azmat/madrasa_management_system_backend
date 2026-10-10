from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class DisciplineCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="discipline_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    default_severity = models.CharField(max_length=20, choices=[("minor", "Minor"), ("moderate", "Moderate"), ("major", "Major"), ("critical", "Critical")], default="minor")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_discipline_category_code")]


class DisciplineIncident(models.Model):
    class Status(models.TextChoices):
        REPORTED = "reported", "رپورٹ شدہ"
        INVESTIGATING = "investigating", "زیر تحقیق"
        ACTION_PENDING = "action_pending", "کارروائی مطلوب"
        RESOLVED = "resolved", "حل شدہ"
        APPEALED = "appealed", "اپیل"
        CLOSED = "closed", "بند"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="discipline_incidents")
    incident_number = models.CharField(max_length=50)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="discipline_incidents")
    category = models.ForeignKey(DisciplineCategory, on_delete=models.PROTECT, related_name="incidents")
    incident_date = models.DateField(default=timezone.localdate)
    location = models.CharField(max_length=200, blank=True)
    severity = models.CharField(max_length=20, choices=DisciplineCategory._meta.get_field("default_severity").choices)
    description = models.TextField()
    confidential = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REPORTED, db_index=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_incidents_reported")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_incidents_assigned")
    findings = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    parent_acknowledged_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_incidents_resolved")
    resolved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-incident_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "incident_number"], name="unique_discipline_incident_number")]

    @classmethod
    def issue_number(cls, madrasa):
        year = timezone.localdate().year
        latest = cls.objects.filter(madrasa=madrasa, incident_number__startswith=f"DIS-{madrasa.id}-{year}-").order_by("-id").first()
        value = int(latest.incident_number.rsplit("-", 1)[-1]) + 1 if latest else 1
        return f"DIS-{madrasa.id}-{year}-{value:06d}"


class DisciplineAction(models.Model):
    class ActionType(models.TextChoices):
        WARNING = "warning", "تنبیہ"
        COUNSELLING = "counselling", "مشاورت"
        PARENT_MEETING = "parent_meeting", "والدین ملاقات"
        COMMUNITY_SERVICE = "community_service", "خدمت"
        SUSPENSION = "suspension", "معطلی"
        OTHER = "other", "دیگر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="discipline_actions")
    incident = models.ForeignKey(DisciplineIncident, on_delete=models.PROTECT, related_name="actions")
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField()
    starts_on = models.DateField(blank=True, null=True)
    ends_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[("planned", "Planned"), ("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="planned")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_actions_assigned")
    completed_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)


class DisciplineAppeal(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="discipline_appeals")
    incident = models.ForeignKey(DisciplineIncident, on_delete=models.PROTECT, related_name="appeals")
    guardian = models.ForeignKey("guardians.GuardianProfile", on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_appeals")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=[("submitted", "Submitted"), ("accepted", "Accepted"), ("rejected", "Rejected")], default="submitted")
    decision = models.TextField(blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="discipline_appeals_decided")
    decided_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TrainingProgram(models.Model):
    class Audience(models.TextChoices):
        STAFF = "staff", "عملہ"
        STUDENTS = "students", "طلبہ"
        BOTH = "both", "دونوں"
        ALUMNI = "alumni", "سابق طلبہ"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        OPEN = "open", "داخلہ جاری"
        ACTIVE = "active", "جاری"
        COMPLETED = "completed", "مکمل"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="training_programs")
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=20, choices=Audience.choices)
    trainer_name = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(default=0)
    certificate_enabled = models.BooleanField(default=True)
    passing_score = models.DecimalField(max_digits=5, decimal_places=2, default=50)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="training_programs_created")
    created_at = models.DateTimeField(auto_now_add=True)


class TrainingEnrollment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="training_enrollments")
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name="enrollments")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="training_enrollments")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="training_enrollments")
    alumni = models.ForeignKey("students.AlumniProfile", on_delete=models.PROTECT, blank=True, null=True, related_name="training_enrollments")
    status = models.CharField(max_length=20, choices=[("enrolled", "Enrolled"), ("attended", "Attended"), ("completed", "Completed"), ("failed", "Failed"), ("withdrawn", "Withdrawn")], default="enrolled")
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    assessment_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    certificate_number = models.CharField(max_length=60, blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["program", "staff"], condition=models.Q(staff__isnull=False), name="unique_staff_training_enrollment"),
            models.UniqueConstraint(fields=["program", "student"], condition=models.Q(student__isnull=False), name="unique_student_training_enrollment"),
            models.UniqueConstraint(fields=["program", "alumni"], condition=models.Q(alumni__isnull=False), name="unique_alumni_training_enrollment"),
        ]


class RewardCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="reward_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    recipient_kind = models.CharField(max_length=20, choices=[("student", "Student"), ("staff", "Staff"), ("alumni", "Alumni"), ("any", "Any")], default="any")
    default_points = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_reward_category_code")]


class RewardNomination(models.Model):
    class Status(models.TextChoices):
        NOMINATED = "nominated", "نامزد"
        APPROVED = "approved", "منظور"
        REJECTED = "rejected", "نامنظور"
        AWARDED = "awarded", "عطا شدہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="reward_nominations")
    category = models.ForeignKey(RewardCategory, on_delete=models.PROTECT, related_name="nominations")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="reward_nominations")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="reward_nominations")
    alumni = models.ForeignKey("students.AlumniProfile", on_delete=models.PROTECT, blank=True, null=True, related_name="reward_nominations")
    title = models.CharField(max_length=250)
    citation = models.TextField()
    points = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOMINATED)
    nominated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="reward_nominations_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="reward_nominations_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    awarded_at = models.DateTimeField(blank=True, null=True)
    certificate_number = models.CharField(max_length=60, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def recipient_name(self):
        target = self.student or self.staff or self.alumni
        if self.alumni_id:
            return self.alumni.student.full_name
        return target.full_name if target else ""


class AlumniEngagement(models.Model):
    class EngagementType(models.TextChoices):
        EVENT = "event", "تقریب"
        VOLUNTEER = "volunteer", "رضاکار"
        MENTORSHIP = "mentorship", "رہنمائی"
        DONATION = "donation", "عطیہ"
        VISIT = "visit", "دورہ"
        OTHER = "other", "دیگر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="alumni_engagements")
    alumni = models.ForeignKey("students.AlumniProfile", on_delete=models.PROTECT, related_name="engagements")
    engagement_type = models.CharField(max_length=20, choices=EngagementType.choices)
    title = models.CharField(max_length=250)
    date = models.DateField(default=timezone.localdate)
    details = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="alumni_engagements_recorded")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
