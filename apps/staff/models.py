from django.conf import settings
from django.db import models


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

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)

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
