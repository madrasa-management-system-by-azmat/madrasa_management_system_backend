from django.conf import settings
from django.db import models


class Taqreeb(models.Model):
    class EventType(models.TextChoices):
        GRADUATION = "graduation", "دستار فضیلت و تقسیم اسناد"
        BUKHARI_KHATM = "bukhari_khatm", "ختم بخاری شریف"
        ANNUAL = "annual", "سالانہ تقریب / جلسہ"
        SEERAT = "seerat", "سیرت النبی کانفرنس"
        COMPETITION = "competition", "مسابقہ / مقابلہ"
        WELCOME = "welcome", "استقبالیہ تقریب"
        FAREWELL = "farewell", "الوداعی تقریب"
        GENERAL = "general", "عام تقریب"

    class Status(models.TextChoices):
        PLANNED = "planned", "منصوبہ بندی"
        IN_PROGRESS = "in_progress", "جاری"
        COMPLETED = "completed", "مکمل"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey(
        "users.Madrasa",
        on_delete=models.CASCADE,
        related_name="taqreeb_events",
    )
    title = models.CharField(max_length=250)
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        default=EventType.GENERAL,
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )
    event_date = models.DateField(db_index=True)
    hijri_date = models.CharField(max_length=100, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    chief_guest = models.CharField(max_length=200, blank=True)
    president = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_taqreebs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_date", "-id"]
        verbose_name = "تقریب"
        verbose_name_plural = "تقریبات"

    def __str__(self):
        return f"{self.title} ({self.event_date})"


class DutyCategory(models.Model):
    madrasa = models.ForeignKey(
        "users.Madrasa",
        on_delete=models.CASCADE,
        related_name="duty_categories",
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=20, default="#1e3a8a")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["madrasa", "name"],
                name="unique_duty_category_per_madrasa",
            )
        ]
        verbose_name = "ڈیوٹی شعبہ"
        verbose_name_plural = "ڈیوٹی شعبہ جات"

    def __str__(self):
        return self.name


class DutyAssignment(models.Model):
    class AssigneeType(models.TextChoices):
        STUDENT = "student", "طالب علم"
        TEACHER = "teacher", "استاد / عملہ"

    class Status(models.TextChoices):
        ASSIGNED = "assigned", "مقرر"
        ACTIVE = "active", "ڈیوٹی پر موجود"
        COMPLETED = "completed", "مکمل"
        ABSENT = "absent", "غیر حاضر"

    madrasa = models.ForeignKey(
        "users.Madrasa",
        on_delete=models.CASCADE,
        related_name="taqreeb_duty_assignments",
    )
    taqreeb = models.ForeignKey(
        Taqreeb,
        on_delete=models.CASCADE,
        related_name="duties",
    )
    duty_category = models.ForeignKey(
        DutyCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments",
    )
    duty_title = models.CharField(max_length=150)
    assignee_type = models.CharField(
        max_length=20,
        choices=AssigneeType.choices,
        default=AssigneeType.STUDENT,
        db_index=True,
    )
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="taqreeb_duties",
    )
    staff = models.ForeignKey(
        "staff.Staff",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="taqreeb_duties",
    )
    card_number = models.CharField(max_length=50, blank=True, db_index=True)
    location = models.CharField(max_length=150, blank=True)
    reporting_time = models.CharField(max_length=50, blank=True)
    instructions = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["taqreeb", "student"],
                condition=models.Q(student__isnull=False),
                name="unique_student_duty_per_taqreeb",
            ),
            models.UniqueConstraint(
                fields=["taqreeb", "staff"],
                condition=models.Q(staff__isnull=False),
                name="unique_staff_duty_per_taqreeb",
            ),
        ]
        verbose_name = "ڈیوٹی تفویض"
        verbose_name_plural = "ڈیوٹی تفویضات"

    def __str__(self):
        assignee_name = (
            self.student.full_name if self.student else (self.staff.full_name if self.staff else "—")
        )
        return f"{assignee_name} - {self.duty_title} ({self.taqreeb.title})"

    def save(self, *args, **kwargs):
        if not self.card_number and self.taqreeb_id:
            super().save(*args, **kwargs)
            self.card_number = f"TQB-{self.taqreeb_id}-{self.id:04d}"
            DutyAssignment.objects.filter(pk=self.pk).update(card_number=self.card_number)
            return
        super().save(*args, **kwargs)


class GuestInvitation(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "مدعو"
        CONFIRMED = "confirmed", "تصدیق شدہ"
        ATTENDED = "attended", "شرکت کی"
        CANCELLED = "cancelled", "معذرت"

    madrasa = models.ForeignKey(
        "users.Madrasa",
        on_delete=models.CASCADE,
        related_name="taqreeb_guest_invitations",
    )
    taqreeb = models.ForeignKey(
        Taqreeb,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    guest_name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    invitation_number = models.CharField(max_length=50, blank=True, db_index=True)
    seat_number = models.CharField(max_length=50, blank=True)
    is_special_guest = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INVITED,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "دعوت نامہ"
        verbose_name_plural = "دعوت نامے"

    def __str__(self):
        return f"{self.guest_name} - {self.taqreeb.title}"

    def save(self, *args, **kwargs):
        if not self.invitation_number and self.taqreeb_id:
            super().save(*args, **kwargs)
            self.invitation_number = f"INV-{self.taqreeb_id}-{self.id:04d}"
            GuestInvitation.objects.filter(pk=self.pk).update(invitation_number=self.invitation_number)
            return
        super().save(*args, **kwargs)

