from django.db import models


class InternalExam(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="internal_exams", null=True, blank=True)
    name = models.CharField(max_length=200)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.CASCADE, related_name="internal_exams", blank=True, null=True)
    classes = models.ManyToManyField("students.AcademicClass", related_name="multi_class_internal_exams", blank=True)
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="internal_exams", blank=True, null=True)
    subjects = models.ManyToManyField("academics.Subject", related_name="multi_subject_internal_exams", blank=True)
    exam_date = models.DateField()

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
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.PENDING)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "student", "subject"], name="unique_internal_result_per_subject")
        ]


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
