from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class InstitutionCalendarDay(models.Model):
    class DayType(models.TextChoices):
        WORKING = "working", "Working day"
        WEEKEND = "weekend", "Weekend"
        PUBLIC_HOLIDAY = "public_holiday", "Public holiday"
        INSTITUTION_HOLIDAY = "institution_holiday", "Institution holiday"
        CLOSURE = "closure", "Closure"

    class Audience(models.TextChoices):
        ALL = "all", "All"
        STAFF = "staff", "Staff"
        STUDENTS = "students", "Students"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="institution_calendar_days")
    date = models.DateField()
    day_type = models.CharField(max_length=30, choices=DayType.choices)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.PROTECT, blank=True, null=True, related_name="calendar_days")
    name = models.CharField(max_length=200)
    counts_as_leave_day = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="calendar_days_created")

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "date", "audience", "academic_class"], name="unique_institution_calendar_day")]


class LeaveType(models.Model):
    class SubjectKind(models.TextChoices):
        STAFF = "staff", "Staff"
        STUDENT = "student", "Student"
        BOTH = "both", "Both"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_types")
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=150)
    subject_kind = models.CharField(max_length=20, choices=SubjectKind.choices, default=SubjectKind.BOTH)
    is_paid = models.BooleanField(default=True)
    paid_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    requires_attachment = models.BooleanField(default=False)
    attachment_required_after_days = models.PositiveSmallIntegerField(default=0)
    allow_half_day = models.BooleanField(default=True)
    allow_negative_balance = models.BooleanField(default=False)
    requires_substitution = models.BooleanField(default=False)
    attendance_status = models.CharField(max_length=20, choices=[("leave", "Leave"), ("sick", "Sick")], default="leave")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject_kind", "name"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "code"], name="unique_leave_type_code_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "name"], name="unique_leave_type_name_per_madrasa"),
        ]


class LeavePolicy(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_policies")
    name = models.CharField(max_length=150)
    subject_kind = models.CharField(max_length=20, choices=LeaveType.SubjectKind.choices)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    working_weekdays = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_policies_created")

    class Meta:
        ordering = ["-effective_from", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name", "effective_from"], name="unique_leave_policy_period")]


class LeavePolicyRule(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_policy_rules")
    policy = models.ForeignKey(LeavePolicy, on_delete=models.CASCADE, related_name="rules")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="policy_rules")
    annual_entitlement = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    maximum_consecutive_days = models.PositiveSmallIntegerField(default=0)
    minimum_notice_days = models.PositiveSmallIntegerField(default=0)
    carry_forward_limit = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["policy", "leave_type"], name="unique_leave_policy_rule")]


class LeaveBalance(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_balances")
    staff = models.ForeignKey("staff.Staff", on_delete=models.CASCADE, blank=True, null=True, related_name="leave_balances")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, blank=True, null=True, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="balances")
    year = models.PositiveSmallIntegerField()
    opening = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    entitlement = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    used = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    adjusted = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["staff", "leave_type", "year"], condition=models.Q(staff__isnull=False), name="unique_staff_leave_balance"),
            models.UniqueConstraint(fields=["student", "leave_type", "year"], condition=models.Q(student__isnull=False), name="unique_student_leave_balance"),
        ]

    @property
    def available(self):
        return self.opening + self.entitlement + self.adjusted - self.used


class LeaveRequest(models.Model):
    class SubjectKind(models.TextChoices):
        STAFF = "staff", "Staff"
        STUDENT = "student", "Student"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        SUBMITTED = "submitted", "جمع شدہ"
        PENDING_APPROVAL = "pending_approval", "منظوری کے لیے"
        APPROVED = "approved", "منظور"
        REJECTED = "rejected", "نامنظور"
        CANCELLED = "cancelled", "منسوخ"

    class DayPart(models.TextChoices):
        FULL = "full", "پورا دن"
        FIRST_HALF = "first_half", "پہلا نصف"
        SECOND_HALF = "second_half", "دوسرا نصف"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_requests")
    request_number = models.CharField(max_length=50)
    subject_kind = models.CharField(max_length=20, choices=SubjectKind.choices)
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="leave_requests")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="leave_requests")
    guardian = models.ForeignKey("guardians.GuardianProfile", on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    starts_on = models.DateField()
    ends_on = models.DateField()
    day_part = models.CharField(max_length=20, choices=DayPart.choices, default=DayPart.FULL)
    chargeable_days = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    reason = models.TextField()
    contact_during_leave = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_requests_submitted")
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_requests_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    rejected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_requests_rejected")
    rejected_at = models.DateTimeField(blank=True, null=True)
    decision_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_requests_cancelled")
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "request_number"], name="unique_leave_request_number_per_madrasa")]

    @classmethod
    def issue_number(cls, madrasa):
        year = timezone.localdate().year
        with transaction.atomic():
            latest = cls.objects.select_for_update().filter(madrasa=madrasa, request_number__startswith=f"LEV-{madrasa.id}-{year}-").order_by("-id").first()
            value = int(latest.request_number.rsplit("-", 1)[-1]) + 1 if latest else 1
            return f"LEV-{madrasa.id}-{year}-{value:06d}"


class LeaveRequestDay(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_request_days")
    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    units = models.DecimalField(max_digits=3, decimal_places=2, default=1)
    is_chargeable = models.BooleanField(default=True)
    calendar_day = models.ForeignKey(InstitutionCalendarDay, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_days")

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["request", "date"], name="unique_leave_request_date")]


class LeaveSubstitution(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_substitutions")
    request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name="substitutions")
    date = models.DateField()
    teaching_assignment = models.ForeignKey("staff.TeachingAssignment", on_delete=models.PROTECT, blank=True, null=True, related_name="leave_substitutions")
    substitute_staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="leave_substitutions")
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_substitutions_assigned")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["request", "date", "teaching_assignment"], name="unique_leave_substitution")]


class LeaveAttachment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_attachments")
    request = models.ForeignKey(LeaveRequest, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(upload_to="leaves/attachments/")
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_attachments_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class LeaveAuditEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="leave_audit_events")
    request = models.ForeignKey(LeaveRequest, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=60)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="leave_audit_events")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
