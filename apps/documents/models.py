from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


def document_upload_path(instance, filename):
    return f"documents/{instance.madrasa_id}/{instance.document_id}/{instance.version}/{filename}"


class DocumentCategory(models.Model):
    class Confidentiality(models.TextChoices):
        INTERNAL = "internal", "داخلی"
        RESTRICTED = "restricted", "محدود"
        CONFIDENTIAL = "confidential", "خفیہ"
        PUBLIC = "public", "عام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, blank=True, null=True, related_name="children")
    default_confidentiality = models.CharField(max_length=20, choices=Confidentiality.choices, default=Confidentiality.INTERNAL)
    default_retention_years = models.PositiveSmallIntegerField(default=5)
    requires_approval = models.BooleanField(default=False)
    allowed_extensions = models.CharField(max_length=250, default="pdf,doc,docx,xls,xlsx,ppt,pptx,txt,jpg,jpeg,png")
    maximum_size_bytes = models.PositiveIntegerField(default=10 * 1024 * 1024)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_document_category_per_madrasa")]

    def __str__(self):
        return self.name


class DocumentFolder(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_folders")
    name = models.CharField(max_length=150)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, blank=True, null=True, related_name="children")
    description = models.TextField(blank=True)
    inherit_access = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="document_folders_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "parent", "name"], name="unique_document_folder_per_parent")]

    def __str__(self):
        return self.name


class DocumentNumberSequence(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_number_sequences")
    year = models.PositiveSmallIntegerField()
    next_value = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["madrasa", "year"], name="unique_document_sequence_year")]


class Document(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "مسودہ"
        IN_REVIEW = "in_review", "زیر جائزہ"
        CHANGES_REQUESTED = "changes_requested", "ترمیم مطلوب"
        APPROVED = "approved", "منظور"
        PUBLISHED = "published", "شائع شدہ"
        EXPIRED = "expired", "میعاد ختم"
        ARCHIVED = "archived", "محفوظ"
        WITHDRAWN = "withdrawn", "واپس لیا گیا"

    class Confidentiality(models.TextChoices):
        INTERNAL = "internal", "داخلی"
        RESTRICTED = "restricted", "محدود"
        CONFIDENTIAL = "confidential", "خفیہ"
        PUBLIC = "public", "عام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="documents")
    document_number = models.CharField(max_length=50)
    sequence_year = models.PositiveSmallIntegerField()
    sequence_number = models.PositiveIntegerField()
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    category = models.ForeignKey(DocumentCategory, on_delete=models.PROTECT, related_name="documents")
    folder = models.ForeignKey(DocumentFolder, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True)
    confidentiality = models.CharField(max_length=20, choices=Confidentiality.choices, default=Confidentiality.INTERNAL, db_index=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="documents_owned")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_to_review")
    effective_date = models.DateField(blank=True, null=True)
    expires_on = models.DateField(blank=True, null=True, db_index=True)
    retention_until = models.DateField(blank=True, null=True)
    keywords = models.CharField(max_length=500, blank=True)
    current_version_number = models.PositiveIntegerField(default=0)
    checked_out_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_checked_out")
    checked_out_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_published")
    published_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="documents_updated")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "document_number"], name="unique_document_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "sequence_year", "sequence_number"], name="unique_document_sequence_number"),
        ]

    @classmethod
    def issue_number(cls, madrasa, year=None):
        year = year or timezone.localdate().year
        with transaction.atomic():
            sequence, _ = DocumentNumberSequence.objects.select_for_update().get_or_create(madrasa=madrasa, year=year, defaults={"next_value": 1})
            value = sequence.next_value
            sequence.next_value += 1
            sequence.save(update_fields=["next_value"])
        return year, value, f"DOC-{madrasa.id}-{year}-{value:06d}"

    def __str__(self):
        return f"{self.document_number} — {self.title}"


class DocumentVersion(models.Model):
    class ScanStatus(models.TextChoices):
        PENDING = "pending", "زیر جانچ"
        CLEAN = "clean", "محفوظ"
        REJECTED = "rejected", "مسترد"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_versions")
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    file = models.FileField(upload_to=document_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=150, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64)
    change_summary = models.CharField(max_length=500, blank=True)
    scan_status = models.CharField(max_length=20, choices=ScanStatus.choices, default=ScanStatus.CLEAN)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="document_versions_uploaded")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["document", "version"], name="unique_document_version")]


class DocumentAccessGrant(models.Model):
    class Permission(models.TextChoices):
        VIEW = "view", "دیکھیں"
        EDIT = "edit", "ترمیم"
        APPROVE = "approve", "منظور"
        MANAGE = "manage", "انتظام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_access_grants")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="access_grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="document_access_grants")
    permission = models.CharField(max_length=20, choices=Permission.choices, default=Permission.VIEW)
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="document_access_grants_created")
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "user"], name="unique_document_access_grant")]


class DocumentLink(models.Model):
    class LinkType(models.TextChoices):
        STUDENT = "student", "طالب علم"
        STAFF = "staff", "عملہ"
        MEETING = "meeting", "اجلاس"
        FATWA = "fatwa", "فتویٰ"
        TASK = "task", "انتظامی کام"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_links")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="links")
    link_type = models.CharField(max_length=20, choices=LinkType.choices)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="document_links")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="document_links")
    meeting = models.ForeignKey("meetings.Meeting", on_delete=models.PROTECT, blank=True, null=True, related_name="document_links")
    fatwa = models.ForeignKey("fatwas.FatwaInquiry", on_delete=models.PROTECT, blank=True, null=True, related_name="document_links")
    task = models.ForeignKey("tasks.AdministrativeTask", on_delete=models.PROTECT, blank=True, null=True, related_name="document_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class DocumentComment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_comments")
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="comments")
    body = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="document_comments_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]


class DocumentAcknowledgement(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_acknowledgements")
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="acknowledgements")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="document_acknowledgements")
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "user"], name="unique_document_acknowledgement")]


class DocumentAuditEvent(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="document_audit_events")
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=60)
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="document_audit_events")
    comment = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
