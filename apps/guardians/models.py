import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class GuardianProfile(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "دعوت دی گئی"
        ACTIVE = "active", "فعال"
        SUSPENDED = "suspended", "معطل"
        REVOKED = "revoked", "منسوخ"

    class Language(models.TextChoices):
        URDU = "urdu", "اردو"
        ENGLISH = "english", "English"
        ARABIC = "arabic", "العربية"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_profiles")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="guardian_profile")
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    normalized_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    cnic_last_four = models.CharField(max_length=4, blank=True)
    preferred_language = models.CharField(max_length=20, choices=Language.choices, default=Language.URDU)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INVITED, db_index=True)
    phone_verified_at = models.DateTimeField(blank=True, null=True)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "normalized_phone"], condition=~models.Q(normalized_phone=""), name="unique_guardian_phone_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "email"], condition=~models.Q(email=""), name="unique_guardian_email_per_madrasa"),
        ]

    def __str__(self):
        return self.full_name


class GuardianStudentLink(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_student_links")
    guardian = models.ForeignKey(GuardianProfile, on_delete=models.CASCADE, related_name="student_links")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="guardian_links")
    relationship = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    is_legal_guardian = models.BooleanField(default=True)
    pickup_authorized = models.BooleanField(default=False)
    portal_access_enabled = models.BooleanField(default=True)
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="guardian_links_verified")
    verified_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="guardian_links_revoked")
    revoked_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-is_primary", "student__full_name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "guardian", "student"], name="unique_guardian_student_link")]


class GuardianInvitation(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_invitations")
    guardian = models.ForeignKey(GuardianProfile, on_delete=models.CASCADE, related_name="invitations")
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(blank=True, null=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="guardian_invitations_created")
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, guardian, invited_by, hours=72):
        token = secrets.token_urlsafe(32)
        invitation = cls.objects.create(madrasa=guardian.madrasa, guardian=guardian, token_hash=hashlib.sha256(token.encode()).hexdigest(), expires_at=timezone.now() + timezone.timedelta(hours=hours), invited_by=invited_by)
        return invitation, token

    @classmethod
    def token_digest(cls, token):
        return hashlib.sha256(token.encode()).hexdigest()


class GuardianConsent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_consents")
    guardian = models.ForeignKey(GuardianProfile, on_delete=models.CASCADE, related_name="consents")
    terms_version = models.CharField(max_length=30)
    privacy_version = models.CharField(max_length=30)
    communication_consent = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-accepted_at"]


class GuardianNotificationPreference(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_notification_preferences")
    guardian = models.OneToOneField(GuardianProfile, on_delete=models.CASCADE, related_name="notification_preferences")
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=True)
    sms = models.BooleanField(default=False)
    attendance = models.BooleanField(default=True)
    results = models.BooleanField(default=True)
    fees = models.BooleanField(default=True)
    hifz = models.BooleanField(default=True)
    meetings = models.BooleanField(default=True)
    announcements = models.BooleanField(default=True)


class ParentMeetingSlot(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "دستیاب"
        CLOSED = "closed", "بند"
        CANCELLED = "cancelled", "منسوخ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="parent_meeting_slots")
    teacher = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="parent_meeting_slots")
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.PROTECT, blank=True, null=True, related_name="parent_meeting_slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    venue = models.CharField(max_length=200, blank=True)
    online_url = models.URLField(blank=True)
    capacity = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="parent_meeting_slots_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]


class ParentMeetingBooking(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "محفوظ"
        CONFIRMED = "confirmed", "تصدیق شدہ"
        COMPLETED = "completed", "مکمل"
        CANCELLED = "cancelled", "منسوخ"
        NO_SHOW = "no_show", "غیر حاضر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="parent_meeting_bookings")
    slot = models.ForeignKey(ParentMeetingSlot, on_delete=models.PROTECT, related_name="bookings")
    guardian = models.ForeignKey(GuardianProfile, on_delete=models.PROTECT, related_name="meeting_bookings")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="parent_meeting_bookings")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.BOOKED)
    agenda = models.TextField(blank=True)
    guardian_notes = models.TextField(blank=True)
    teacher_notes = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    follow_up_due = models.DateField(blank=True, null=True)
    booked_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-slot__starts_at"]
        constraints = [models.UniqueConstraint(fields=["slot", "guardian", "student"], name="unique_parent_meeting_booking")]


class GuardianAnnouncement(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "تمام والدین"
        CLASS = "class", "جماعت"
        INDIVIDUAL = "individual", "انفرادی"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_announcements")
    title = models.CharField(max_length=250)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    academic_class = models.ForeignKey("students.AcademicClass", on_delete=models.PROTECT, blank=True, null=True, related_name="guardian_announcements")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="guardian_announcements")
    published_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="guardian_announcements_created")

    class Meta:
        ordering = ["-published_at"]


class GuardianAnnouncementRead(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="guardian_announcement_reads")
    announcement = models.ForeignKey(GuardianAnnouncement, on_delete=models.CASCADE, related_name="reads")
    guardian = models.ForeignKey(GuardianProfile, on_delete=models.CASCADE, related_name="announcement_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["announcement", "guardian"], name="unique_guardian_announcement_read")]
