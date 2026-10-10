from django.conf import settings
from django.db import models
from django.utils import timezone


class InternalExam(models.Model):
    class ExamType(models.TextChoices):
        MONTHLY = "monthly", "ماہانہ"
        QUARTERLY = "quarterly", "سہ ماہی"
        HALF_YEARLY = "half_yearly", "ششماہی"
        ANNUAL = "annual", "سالانہ"
        ADMISSION = "admission", "داخلہ ٹیسٹ"
        ORAL = "oral", "زبانی"
        HIFZ = "hifz", "حفظ"
        NAZRA = "nazra", "ناظرہ"
        TAJWEED = "tajweed", "تجوید"
        SPECIAL = "special", "خصوصی"

    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        PLANNED = "planned", "منصوبہ بند"
        OPEN = "open", "نمبر اندراج جاری"
        VERIFIED = "verified", "تصدیق شدہ"
        FINALIZED = "finalized", "حتمی"
        PUBLISHED = "published", "جاری شدہ"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="internal_exams", null=True, blank=True)
    name = models.CharField(max_length=200)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.CASCADE, related_name="internal_exams", blank=True, null=True)
    classes = models.ManyToManyField("students.AcademicClass", related_name="multi_class_internal_exams", blank=True)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="internal_exams", blank=True, null=True)
    subjects = models.ManyToManyField("academics.Subject", related_name="multi_subject_internal_exams", blank=True)
    exam_date = models.DateField()
    academic_year = models.ForeignKey("students.AcademicYear", on_delete=models.PROTECT, blank=True, null=True, related_name="internal_exams")
    exam_type = models.CharField(max_length=20, choices=ExamType.choices, default=ExamType.SPECIAL)
    term = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    instructions = models.TextField(blank=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exams_finalized")
    finalized_at = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-exam_date", "name"]

    def __str__(self):
        return self.name


class InternalExamPaper(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="exam_papers", null=True, blank=True)
    exam = models.ForeignKey(InternalExam, on_delete=models.CASCADE, related_name="papers")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="exam_papers")
    paper_date = models.DateField()
    paper_time = models.TimeField(blank=True, null=True)
    duration_minutes = models.PositiveSmallIntegerField(default=120)
    total_marks_snapshot = models.PositiveIntegerField(blank=True, null=True)
    passing_marks_snapshot = models.PositiveIntegerField(blank=True, null=True)
    class_offering = models.ForeignKey("academics.ClassOffering", on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_papers")
    room = models.CharField(max_length=100, blank=True)
    syllabus_units = models.ManyToManyField("academics.CurriculumUnit", blank=True, related_name="exam_papers")
    question_paper = models.FileField(upload_to="exams/question-papers/", blank=True, null=True)
    answer_key = models.FileField(upload_to="exams/answer-keys/", blank=True, null=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_papers_prepared")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_papers_approved")
    approved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["paper_date", "paper_time", "subject__academic_class__name", "subject__name"]
        constraints = [
            models.UniqueConstraint(fields=["exam", "subject"], name="unique_exam_subject_paper")
        ]


class InternalExamResult(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="exam_results", null=True, blank=True)
    class Result(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"
        PENDING = "pending", "Pending"

    exam = models.ForeignKey(InternalExam, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="internal_exam_results")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, blank=True, null=True, related_name="exam_results")
    marks = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.PENDING)
    enrollment = models.ForeignKey("students.StudentEnrollment", on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_results")
    paper = models.ForeignKey(InternalExamPaper, on_delete=models.SET_NULL, blank=True, null=True, related_name="results")
    roll_number_snapshot = models.CharField(max_length=50, blank=True)
    is_absent = models.BooleanField(default=False)
    is_exempt = models.BooleanField(default=False)
    remarks = models.CharField(max_length=255, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_results_entered")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_results_verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "student", "subject"], name="unique_internal_result_per_subject")
        ]


class ExamDuty(models.Model):
    class DutyType(models.TextChoices):
        SETTER = "setter", "پرچہ ساز"
        MODERATOR = "moderator", "مصحح"
        INVIGILATOR = "invigilator", "نگران"
        CHECKER = "checker", "جانچ کنندہ"
        SUPERVISOR = "supervisor", "امتحانی ناظم"

    class Status(models.TextChoices):
        ASSIGNED = "assigned", "مقرر"
        COMPLETED = "completed", "مکمل"
        MISSED = "missed", "غیر حاضر"
        EXCUSED = "excused", "معذور"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="exam_duties")
    exam = models.ForeignKey(InternalExam, on_delete=models.CASCADE, related_name="duties")
    paper = models.ForeignKey(InternalExamPaper, on_delete=models.CASCADE, blank=True, null=True, related_name="duties")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="exam_duties")
    duty_type = models.CharField(max_length=20, choices=DutyType.choices)
    room = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_duties_assigned")
    remarks = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["paper", "staff", "duty_type"], name="unique_exam_paper_staff_duty")]


class ExamAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غیر حاضر"
        EXEMPT = "exempt", "مستثنیٰ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="exam_attendance")
    paper = models.ForeignKey(InternalExamPaper, on_delete=models.CASCADE, related_name="attendance")
    enrollment = models.ForeignKey("students.StudentEnrollment", on_delete=models.PROTECT, related_name="exam_attendance")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    seat_number = models.CharField(max_length=30, blank=True)
    room = models.CharField(max_length=100, blank=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_attendance_marked")
    marked_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["paper", "enrollment"], name="unique_exam_paper_enrollment_attendance")]


class ExamResultChange(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="exam_result_changes")
    result = models.ForeignKey(InternalExamResult, on_delete=models.PROTECT, related_name="changes")
    old_marks = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    new_marks = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    old_result = models.CharField(max_length=10, blank=True)
    new_result = models.CharField(max_length=10, blank=True)
    reason = models.CharField(max_length=250)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="exam_result_changes")
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]


class AnnualResult(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="annual_results")
    enrollment = models.OneToOneField("students.StudentEnrollment", on_delete=models.PROTECT, related_name="annual_result")
    total_marks = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    obtained_marks = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    grade = models.CharField(max_length=20, blank=True)
    rank = models.PositiveIntegerField(blank=True, null=True)
    result = models.CharField(max_length=20, choices=InternalExamResult.Result.choices, default=InternalExamResult.Result.PENDING)
    promotion_eligible = models.BooleanField(default=False)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="annual_results_finalized")
    finalized_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WafaqBoardRegistration(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="wafaq_registrations", null=True, blank=True)
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"

    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="wafaq_registrations")
    wafaq_name = models.CharField(max_length=200)
    roll_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-id"]


class WafaqResult(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="wafaq_results", null=True, blank=True)
    registration = models.OneToOneField(WafaqBoardRegistration, on_delete=models.CASCADE, related_name="result")
    passing_year = models.PositiveSmallIntegerField()
    result = models.CharField(max_length=100)
