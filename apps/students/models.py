from django.db import models


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

    registration_number = models.CharField(max_length=20, unique=True, editable=False)
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
            last_student = Student.objects.order_by("-id").first()
            next_number = (last_student.id + 1) if last_student else 1
            self.registration_number = f"ST-{next_number:04d}"

        super().save(*args, **kwargs)


class StudentAttendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "حاضر"
        ABSENT = "absent", "غیر حاضر"
        LEAVE = "leave", "رخصت"

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
