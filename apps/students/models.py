from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Department(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="departments", null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicClass(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="academic_classes", null=True, blank=True)
    name = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="classes",
    )
    tuition_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hostel_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["department__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"],
                name="unique_class_per_department",
            )
        ]

    def __str__(self):
        return f"{self.department} — {self.name}"


class Halaqa(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="halaqas", null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    ustad_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Student(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="students", null=True, blank=True)
    class Gender(models.TextChoices):
        MALE = "male", "طالب"
        FEMALE = "female", "طالبہ"

    class ResidentialStatus(models.TextChoices):
        DAY_SCHOLAR = "day_scholar", "روزانہ آنے والا"
        RESIDENT = "resident", "ہاسٹل میں مقیم"

    class Status(models.TextChoices):
        ACTIVE = "active", "فعال"
        ON_LEAVE = "on_leave", "رخصت"
        INACTIVE = "inactive", "غیر فعال"

    class LifecycleStatus(models.TextChoices):
        ADMITTED = "admitted", "داخلہ منظور"
        ENROLLED = "enrolled", "زیر تعلیم"
        ON_LEAVE = "on_leave", "رخصت پر"
        WITHDRAWN = "withdrawn", "تعلیم ترک"
        TRANSFERRED = "transferred", "منتقل"
        COMPLETED = "completed", "تعلیم مکمل"
        GRADUATED = "graduated", "فارغ التحصیل"
        ALUMNI = "alumni", "سابق طالب علم"
        INACTIVE_LEGACY = "inactive_legacy", "سابقہ غیر فعال — جائزہ مطلوب"
        EXPELLED = "expelled", "خارج"
        DECEASED = "deceased", "وفات یافتہ"
        ARCHIVED = "archived", "محفوظ شدہ"

    registration_number = models.CharField(max_length=20, unique=True, editable=False)
    lifecycle_status = models.CharField(max_length=30, choices=LifecycleStatus.choices, default=LifecycleStatus.ENROLLED, db_index=True)
    application_date = models.DateField(blank=True, null=True)
    admitted_at = models.DateTimeField(blank=True, null=True)
    graduation_date = models.DateField(blank=True, null=True)
    alumni_since = models.DateField(blank=True, null=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="students_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="students_updated")
    full_name = models.CharField(max_length=200)
    guardian_name = models.CharField(max_length=200)
    guardian_relation = models.CharField(max_length=100, blank=True)
    guardian_cnic = models.CharField(max_length=20, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    cnic = models.CharField(max_length=20, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=20)
    nationality = models.CharField(max_length=100, blank=True, default="پاکستانی")
    country = models.CharField(max_length=100, blank=True, default="پاکستان")
    religion = models.CharField(max_length=100, blank=True, default="اسلام")
    caste = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField(blank=True, null=True)
    residential_status = models.CharField(
        max_length=20,
        choices=ResidentialStatus.choices,
        default=ResidentialStatus.DAY_SCHOLAR,
    )
    is_mustahiq = models.BooleanField(default=False)
    current_halaqa = models.ForeignKey(
        Halaqa,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="students",
    )
    current_class = models.ForeignKey(
        AcademicClass,
        on_delete=models.PROTECT,
        related_name="students",
    )
    admission_date = models.DateField()
    requested_class = models.CharField(max_length=150, blank=True)
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
    health_conditions = models.TextField(blank=True)
    modern_education = models.TextField(blank=True)
    other_certificates = models.TextField(blank=True)
    previous_madrasas = models.JSONField(default=list, blank=True)
    relatives = models.JSONField(default=list, blank=True)
    admission_test_report = models.TextField(blank=True)
    office_notes = models.TextField(blank=True)
    admission_decision = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to="students/photos/", blank=True, null=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-admission_date", "full_name"]

    def __str__(self):
        return f"{self.registration_number} — {self.full_name}"

    def save(self, *args, **kwargs):
        if not self.registration_number:
            if not self.madrasa_id:
                raise ValueError("A madrasa is required before issuing a student ID.")
            with transaction.atomic():
                sequence, _ = StudentNumberSequence.objects.select_for_update().get_or_create(
                    madrasa_id=self.madrasa_id,
                    defaults={"next_value": 1},
                )
                self.registration_number = f"M{self.madrasa_id}-ST-{sequence.next_value:04d}"
                sequence.next_value += 1
                sequence.save(update_fields=["next_value"])

        super().save(*args, **kwargs)


class StudentNumberSequence(models.Model):
    madrasa = models.OneToOneField("users.Madrasa", on_delete=models.CASCADE, related_name="student_number_sequence")
    next_value = models.PositiveBigIntegerField(default=1)


class AcademicYear(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "منصوبہ بند"
        OPEN = "open", "جاری"
        CLOSED = "closed", "مکمل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="academic_years")
    name = models.CharField(max_length=50)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-starts_on"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_academic_year_per_madrasa")]

    def __str__(self):
        return self.name


class StudentEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "جاری"
        COMPLETED = "completed", "مکمل"
        PROMOTED = "promoted", "ترقی یافتہ"
        REPEATED = "repeated", "دوبارہ"
        WITHDRAWN = "withdrawn", "ترک تعلیم"
        TRANSFERRED = "transferred", "منتقل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_enrollments")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="enrollments")
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="enrollments")
    halaqa = models.ForeignKey(Halaqa, on_delete=models.SET_NULL, blank=True, null=True, related_name="enrollments")
    roll_number = models.CharField(max_length=50, blank=True)
    started_on = models.DateField()
    ended_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    previous_enrollment = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="next_enrollments")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="student_enrollments_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_on", "student__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["student", "academic_year", "academic_class"], name="unique_student_year_class_enrollment"),
            models.UniqueConstraint(fields=["academic_year", "academic_class", "roll_number"], condition=~models.Q(roll_number=""), name="unique_roll_number_per_year_class"),
        ]


class RollNumberChange(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="roll_number_changes")
    enrollment = models.ForeignKey(StudentEnrollment, on_delete=models.PROTECT, related_name="roll_number_changes")
    old_roll_number = models.CharField(max_length=50, blank=True)
    new_roll_number = models.CharField(max_length=50)
    reason = models.CharField(max_length=250)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="roll_number_changes")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]


class StudentLifecycleEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_lifecycle_events")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="lifecycle_events")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, choices=Student.LifecycleStatus.choices)
    effective_at = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="student_lifecycle_events")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_at", "-id"]


class AdmissionApplication(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "درخواست موصول"
        INTERVIEW_SCHEDULED = "interview_scheduled", "انٹرویو مقرر"
        INTERVIEWED = "interviewed", "انٹرویو مکمل"
        TEST_SCHEDULED = "test_scheduled", "ٹیسٹ مقرر"
        TESTED = "tested", "ٹیسٹ مکمل"
        APPROVED = "approved", "منظور"
        REJECTED = "rejected", "نامنظور"
        WAITLISTED = "waitlisted", "انتظار فہرست"
        ADMITTED = "admitted", "داخلہ مکمل"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="admission_applications")
    application_number = models.CharField(max_length=40)
    application_date = models.DateField(default=timezone.localdate)
    full_name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    guardian_name = models.CharField(max_length=200)
    guardian_relation = models.CharField(max_length=100, blank=True)
    guardian_phone = models.CharField(max_length=20)
    alternate_phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Student.Gender.choices)
    address = models.TextField(blank=True)
    village = models.CharField(max_length=120, blank=True)
    tehsil = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    previous_institution = models.CharField(max_length=250, blank=True)
    previous_education = models.CharField(max_length=250, blank=True)
    requested_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, related_name="admission_applications")
    special_education_needs = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    student = models.OneToOneField(Student, on_delete=models.SET_NULL, blank=True, null=True, related_name="admission_application")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="admission_applications_submitted")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-application_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "application_number"], name="unique_application_number_per_madrasa")]

    def save(self, *args, **kwargs):
        if not self.application_number:
            year = (self.application_date or timezone.localdate()).year
            prefix = f"APP-{self.madrasa_id}-{year}-"
            latest = AdmissionApplication.objects.filter(madrasa_id=self.madrasa_id, application_number__startswith=prefix).order_by("-id").first()
            number = (int(latest.application_number.rsplit("-", 1)[-1]) + 1) if latest else 1
            self.application_number = f"{prefix}{number:04d}"
        super().save(*args, **kwargs)


class AdmissionInterview(models.Model):
    class Attendance(models.TextChoices):
        SCHEDULED = "scheduled", "مقرر"
        ATTENDED = "attended", "حاضر"
        NO_SHOW = "no_show", "غیر حاضر"
        RESCHEDULED = "rescheduled", "دوبارہ مقرر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="admission_interviews")
    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="interviews")
    scheduled_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="admission_interviews")
    attendance_status = models.CharField(max_length=20, choices=Attendance.choices, default=Attendance.SCHEDULED)
    score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    recommendation = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_at"]


class AdmissionTest(models.Model):
    class Outcome(models.TextChoices):
        PENDING = "pending", "زیر التوا"
        PASS = "pass", "کامیاب"
        FAIL = "fail", "ناکام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="admission_tests")
    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="tests")
    scheduled_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    evaluator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="admission_tests")
    total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    obtained_marks = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    passing_marks = models.DecimalField(max_digits=6, decimal_places=2, default=40)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.PENDING)
    attempt_number = models.PositiveSmallIntegerField(default=1)
    report = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["application", "attempt_number"], name="unique_admission_test_attempt")]


class AdmissionDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "منظور"
        REJECTED = "rejected", "نامنظور"
        WAITLISTED = "waitlisted", "انتظار فہرست"
        DEFERRED = "deferred", "مؤخر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="admission_decisions")
    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="decisions")
    decision = models.CharField(max_length=20, choices=Decision.choices)
    decided_at = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="admission_decisions")
    approved_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, blank=True, null=True, related_name="admission_decisions")
    conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-decided_at"]


class PromotionDecision(models.Model):
    class Decision(models.TextChoices):
        PROMOTE = "promote", "ترقی"
        REPEAT = "repeat", "دوبارہ"
        TRANSFER = "transfer", "منتقلی"
        COMPLETE = "complete", "تکمیل"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="promotion_decisions")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="promotion_decisions")
    from_enrollment = models.ForeignKey(StudentEnrollment, on_delete=models.PROTECT, related_name="promotion_decisions")
    target_class = models.ForeignKey(AcademicClass, on_delete=models.PROTECT, blank=True, null=True, related_name="promotion_targets")
    target_academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, blank=True, null=True, related_name="promotion_decisions")
    decision = models.CharField(max_length=20, choices=Decision.choices)
    decided_on = models.DateField(default=timezone.localdate)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="promotion_decisions")
    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(blank=True, null=True)


class GraduationRecord(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="graduation_records")
    student = models.OneToOneField(Student, on_delete=models.PROTECT, related_name="graduation_record")
    enrollment = models.ForeignKey(StudentEnrollment, on_delete=models.PROTECT, related_name="graduation_records")
    completion_date = models.DateField()
    final_result = models.CharField(max_length=100, blank=True)
    distinction = models.CharField(max_length=150, blank=True)
    graduation_number = models.CharField(max_length=50)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="graduation_records_approved")
    approved_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "graduation_number"], name="unique_graduation_number_per_madrasa")]


class AlumniProfile(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="alumni_profiles")
    student = models.OneToOneField(Student, on_delete=models.PROTECT, related_name="alumni_profile")
    graduation_record = models.OneToOneField(GraduationRecord, on_delete=models.PROTECT, related_name="alumni_profile")
    alumni_since = models.DateField()
    current_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    current_address = models.TextField(blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    employer = models.CharField(max_length=200, blank=True)
    further_education = models.TextField(blank=True)
    contact_consent = models.BooleanField(default=True)
    notes = models.TextField(blank=True)


class StudentAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غیر حاضر"
        LEAVE = "leave", "رخصت"
        LATE = "late", "تاخیر"
        SICK = "sick", "بیمار"
        OUTSIDE = "outside", "ادارے سے باہر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_attendance", null=True, blank=True)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "student__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"],
                name="unique_student_attendance_per_day",
            )
        ]

    def __str__(self):
        return f"{self.student} — {self.date} ({self.status})"


class AttendanceAlertRule(models.Model):
    madrasa = models.OneToOneField("users.Madrasa", on_delete=models.CASCADE, related_name="attendance_alert_rule")
    consecutive_absence_threshold = models.PositiveSmallIntegerField(default=3)
    monthly_absence_threshold = models.PositiveSmallIntegerField(default=5)
    monthly_late_threshold = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="attendance_alert_rules_updated")
    updated_at = models.DateTimeField(auto_now=True)


class AttendanceAlert(models.Model):
    class AlertType(models.TextChoices):
        CONSECUTIVE_ABSENCE = "consecutive_absence", "مسلسل غیر حاضری"
        MONTHLY_ABSENCE = "monthly_absence", "ماہانہ زیادہ غیر حاضری"
        REPEATED_LATE = "repeated_late", "مسلسل تاخیر"

    class Severity(models.TextChoices):
        WARNING = "warning", "توجہ"
        HIGH = "high", "اہم"
        CRITICAL = "critical", "فوری"

    class Status(models.TextChoices):
        OPEN = "open", "کھلا"
        ACKNOWLEDGED = "acknowledged", "دیکھ لیا گیا"
        RESOLVED = "resolved", "حل شدہ"
        DISMISSED = "dismissed", "خارج"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="attendance_alerts")
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="attendance_alerts")
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    period_key = models.CharField(max_length=30)
    count = models.PositiveSmallIntegerField(default=0)
    date_from = models.DateField()
    date_to = models.DateField()
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    reason = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="attendance_alerts_acknowledged")
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="attendance_alerts_resolved")
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "alert_type", "period_key"], name="unique_attendance_alert_per_rule_period")
        ]
