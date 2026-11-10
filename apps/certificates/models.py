import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class CertificateNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_number_sequences")
    year = models.PositiveSmallIntegerField()
    prefix = models.CharField(max_length=10)
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year", "prefix"], name="unique_certificate_sequence")]


class Certificate(models.Model):
    class CertificateType(models.TextChoices):
        GRADUATION = "graduation", "Graduation"
        LEAVING = "leaving", "Leaving"
        NAZERA = "nazera", "Nazera Quran"
        HIFZ = "hifz", "Hifz Quran"
        TARJAMA = "tarjama", "Translation Quran"
        TAJWEED = "tajweed", "Tajweed & Qiraat"
        ALIMIYYAH = "alimiyyah", "Alimiyyah"
        ALIMIYYAH_FIRST = "alimiyyah_first", "Alimiyyah First (عالمیہ اول)"
        TRAINING = "training", "Training"
        REWARD = "reward", "Reward"
        MARKSHEET = "marksheet", "Marksheet"
        MANUAL = "manual", "Manual"

    class RecipientKind(models.TextChoices):
        STUDENT = "student", "Student"
        STAFF = "staff", "Staff"
        ALUMNI = "alumni", "Alumni"
        EXTERNAL = "external", "External"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        ISSUED = "issued", "Issued"
        REVOKED = "revoked", "Revoked"
        SUPERSEDED = "superseded", "Superseded"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificates")
    serial_number = models.CharField(max_length=80, unique=True)
    certificate_type = models.CharField(max_length=20, choices=CertificateType.choices)
    recipient_kind = models.CharField(max_length=20, choices=RecipientKind.choices)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    alumni = models.ForeignKey("students.AlumniProfile", on_delete=models.PROTECT, blank=True, null=True, related_name="certificates")
    recipient_name_snapshot = models.CharField(max_length=250)
    recipient_identifier_snapshot = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=250)
    body_snapshot = models.TextField()
    issuer_snapshot = models.JSONField(default=dict)
    credential_snapshot = models.JSONField(default=dict)
    source_type = models.CharField(max_length=50, blank=True)
    source_object_id = models.PositiveBigIntegerField(blank=True, null=True)
    source_fingerprint = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    issued_on = models.DateField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_issued")
    issued_at = models.DateTimeField(blank=True, null=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_revoked")
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.TextField(blank=True)
    supersedes = models.OneToOneField("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="superseded_by")
    revision_number = models.PositiveSmallIntegerField(default=1)
    payload_hash = models.CharField(max_length=64, blank=True)
    signature = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificates_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "source_fingerprint"], condition=~models.Q(source_fingerprint="") & models.Q(status__in=["approved", "issued"]), name="unique_active_source_certificate")]

    @classmethod
    def issue_serial(cls, madrasa, certificate_type):
        prefix_map = {
            "graduation": "GRD",
            "leaving": "LEV",
            "nazera": "NAZ",
            "hifz": "HFZ",
            "tarjama": "TRJ",
            "tajweed": "TJW",
            "alimiyyah": "ALM",
            "alimiyyah_first": "ALM1",
            "training": "TRN",
            "reward": "RWD",
            "marksheet": "MRK",
            "manual": "MAN",
        }
        prefix = prefix_map.get(certificate_type, "CRT")
        year = timezone.localdate().year
        with transaction.atomic():
            sequence, _ = CertificateNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, prefix=prefix, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return f"{madrasa.slug.upper()}-{prefix}-{year}-{value:06d}"


class CertificateEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_events")
    certificate = models.ForeignKey(Certificate, on_delete=models.PROTECT, related_name="events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="certificate_events")
    reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class CertificateVerificationLog(models.Model):
    certificate = models.ForeignKey(Certificate, on_delete=models.CASCADE, related_name="verification_logs")
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="certificate_verification_logs")
    verified_at = models.DateTimeField(auto_now_add=True)
    result = models.CharField(max_length=20, choices=[("valid", "Valid"), ("revoked", "Revoked"), ("invalid", "Invalid")])
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-verified_at"]
