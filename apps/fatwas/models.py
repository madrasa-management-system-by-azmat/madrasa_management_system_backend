from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class FatwaCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, blank=True, null=True, related_name="children")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_fatwa_category_per_madrasa")]

    def __str__(self):
        return self.name


class FatwaTag(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_tags")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_fatwa_tag_per_madrasa")]

    def __str__(self):
        return self.name


class FatwaNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_number_sequences")
    year = models.PositiveSmallIntegerField()
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year"], name="unique_fatwa_sequence_year")]


class FatwaInquiry(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "موصول"
        TRIAGED = "triaged", "درجہ بند"
        ASSIGNED = "assigned", "تفویض شدہ"
        RESEARCHING = "researching", "تحقیق جاری"
        DRAFTING = "drafting", "مسودہ"
        IN_REVIEW = "in_review", "زیر جائزہ"
        CHANGES_REQUESTED = "changes_requested", "ترمیم مطلوب"
        REVIEWED = "reviewed", "جائزہ مکمل"
        APPROVED = "approved", "منظور"
        PUBLISHED = "published", "شائع شدہ"
        REJECTED = "rejected", "مسترد"
        CANCELLED = "cancelled", "منسوخ"
        ARCHIVED = "archived", "محفوظ"

    class Priority(models.TextChoices):
        NORMAL = "normal", "عام"
        URGENT = "urgent", "فوری"
        CRITICAL = "critical", "نہایت فوری"

    class Visibility(models.TextChoices):
        INTERNAL = "internal", "داخلی"
        CONFIDENTIAL = "confidential", "خفیہ"
        PUBLIC = "public", "عام"

    class Channel(models.TextChoices):
        WALK_IN = "walk_in", "بالمشافہ"
        PHONE = "phone", "فون"
        EMAIL = "email", "ای میل"
        LETTER = "letter", "خط"
        WEB = "web", "آن لائن"
        INTERNAL = "internal", "داخلی"

    class Language(models.TextChoices):
        URDU = "urdu", "اردو"
        ARABIC = "arabic", "عربی"
        ENGLISH = "english", "انگریزی"
        OTHER = "other", "دیگر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_inquiries")
    case_number = models.CharField(max_length=50)
    sequence_year = models.PositiveSmallIntegerField()
    sequence_number = models.PositiveIntegerField()
    subject = models.CharField(max_length=300)
    question_text = models.TextField()
    category = models.ForeignKey(FatwaCategory, on_delete=models.PROTECT, related_name="inquiries")
    tags = models.ManyToManyField(FatwaTag, blank=True, related_name="inquiries")
    language = models.CharField(max_length=20, choices=Language.choices, default=Language.URDU)
    channel = models.CharField(max_length=20, choices=Channel.choices, default=Channel.WALK_IN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.INTERNAL)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    assigned_mufti = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwas_assigned_as_mufti")
    assigned_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwas_assigned_as_reviewer")
    received_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwas_published")
    public_slug = models.SlugField(max_length=180, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_inquiries_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_inquiries_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "case_number"], name="unique_fatwa_case_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "sequence_year", "sequence_number"], name="unique_fatwa_sequence_number"),
            models.UniqueConstraint(fields=["madrasa", "public_slug"], condition=~models.Q(public_slug=""), name="unique_fatwa_public_slug_per_madrasa"),
        ]

    @classmethod
    def issue_number(cls, madrasa, year=None):
        year = year or timezone.localdate().year
        with transaction.atomic():
            sequence, _ = FatwaNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return year, value, f"IFT-{madrasa.id}-{year}-{value:06d}"

    def __str__(self):
        return f"{self.case_number} — {self.subject}"


class FatwaRequester(models.Model):
    inquiry = models.OneToOneField(FatwaInquiry, on_delete=models.CASCADE, related_name="requester")
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_requesters")
    name = models.CharField(max_length=200, blank=True)
    guardian_or_organization = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    preferred_contact = models.CharField(max_length=20, choices=[("phone", "Phone"), ("email", "Email"), ("none", "None")], default="phone")
    consent_to_contact = models.BooleanField(default=True)
    consent_to_publish_question = models.BooleanField(default=False)
    anonymize_on_publication = models.BooleanField(default=True)
    confidential_notes = models.TextField(blank=True)


class FatwaRevision(models.Model):
    class RevisionType(models.TextChoices):
        RESEARCH = "research", "تحقیقی نوٹ"
        DRAFT = "draft", "مسودہ"
        REVIEWED = "reviewed", "نظرثانی شدہ"
        APPROVED = "approved", "منظور شدہ جواب"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_revisions")
    inquiry = models.ForeignKey(FatwaInquiry, on_delete=models.PROTECT, related_name="revisions")
    version = models.PositiveIntegerField()
    revision_type = models.CharField(max_length=20, choices=RevisionType.choices, default=RevisionType.DRAFT)
    question_snapshot = models.TextField()
    answer_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    based_on = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="derived_revisions")
    is_current = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_revisions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["inquiry", "version"], name="unique_fatwa_revision_version")]


class FatwaReference(models.Model):
    class ReferenceType(models.TextChoices):
        QURAN = "quran", "قرآن"
        HADITH = "hadith", "حدیث"
        FIQH = "fiqh", "فقہی کتاب"
        FATWA = "fatwa", "سابقہ فتویٰ"
        LAW = "law", "قانون"
        OTHER = "other", "دیگر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_references")
    inquiry = models.ForeignKey(FatwaInquiry, on_delete=models.PROTECT, related_name="references")
    revision = models.ForeignKey(FatwaRevision, on_delete=models.SET_NULL, blank=True, null=True, related_name="references")
    reference_type = models.CharField(max_length=20, choices=ReferenceType.choices)
    title = models.CharField(max_length=250)
    author = models.CharField(max_length=200, blank=True)
    volume = models.CharField(max_length=50, blank=True)
    page = models.CharField(max_length=50, blank=True)
    citation_text = models.TextField(blank=True)
    quotation = models.TextField(blank=True)
    url = models.URLField(blank=True)
    library_book = models.ForeignKey("library.LibraryBook", on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_references")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_references_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class FatwaAttachment(models.Model):
    class Visibility(models.TextChoices):
        INTERNAL = "internal", "داخلی"
        REVIEWER = "reviewer", "جائزہ کنندہ"
        PUBLIC = "public", "عام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_attachments")
    inquiry = models.ForeignKey(FatwaInquiry, on_delete=models.PROTECT, related_name="attachments")
    revision = models.ForeignKey(FatwaRevision, on_delete=models.SET_NULL, blank=True, null=True, related_name="attachments")
    file = models.FileField(upload_to="fatwas/attachments/")
    original_name = models.CharField(max_length=255)
    attachment_type = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.INTERNAL)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_attachments_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)


class FatwaWorkflowEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_workflow_events")
    inquiry = models.ForeignKey(FatwaInquiry, on_delete=models.PROTECT, related_name="workflow_events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_workflow_events")
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class FatwaPublication(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fatwa_publications")
    inquiry = models.OneToOneField(FatwaInquiry, on_delete=models.PROTECT, related_name="publication")
    revision = models.ForeignKey(FatwaRevision, on_delete=models.PROTECT, related_name="publications")
    public_number = models.CharField(max_length=60)
    slug = models.SlugField(max_length=180)
    public_question = models.TextField()
    public_answer = models.TextField()
    public_summary = models.TextField(blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fatwa_publications_created")
    published_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(blank=True, null=True)
    withdrawal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-published_at"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "public_number"], name="unique_fatwa_public_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "slug"], name="unique_fatwa_publication_slug_per_madrasa"),
        ]
