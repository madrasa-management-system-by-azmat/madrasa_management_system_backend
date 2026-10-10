from pathlib import Path

from django.db import transaction
from rest_framework import serializers

from .models import Document, DocumentAccessGrant, DocumentAcknowledgement, DocumentAuditEvent, DocumentCategory, DocumentComment, DocumentFolder, DocumentLink, DocumentVersion


class DocumentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentCategory
        fields = ["id", "name", "code", "description", "parent", "default_confidentiality", "default_retention_years", "requires_approval", "allowed_extensions", "maximum_size_bytes", "is_active", "sort_order"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent and self.instance and parent.id == self.instance.id:
            raise serializers.ValidationError({"parent": "A category cannot be its own parent."})
        return attrs


class DocumentFolderSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(source="documents.count", read_only=True)

    class Meta:
        model = DocumentFolder
        fields = ["id", "name", "parent", "description", "inherit_access", "is_system", "created_by", "created_at", "document_count"]
        read_only_fields = ["created_by", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if parent and self.instance and parent.id == self.instance.id:
            raise serializers.ValidationError({"parent": "A folder cannot be its own parent."})
        return attrs


class DocumentVersionSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ["id", "document", "version", "original_name", "content_type", "size_bytes", "checksum_sha256", "change_summary", "scan_status", "uploaded_by", "uploaded_by_name", "uploaded_at", "download_url"]
        read_only_fields = fields

    def get_download_url(self, version):
        request = self.context.get("request")
        path = f"/api/v1/documents/versions/{version.pk}/download/"
        return request.build_absolute_uri(path) if request else path

    def get_uploaded_by_name(self, version):
        return (version.uploaded_by.get_full_name() or version.uploaded_by.username) if version.uploaded_by else "سسٹم"


class DocumentAccessGrantSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAccessGrant
        fields = ["id", "document", "user", "user_name", "permission", "granted_by", "granted_at", "expires_at"]
        read_only_fields = ["granted_by", "granted_at"]

    def get_user_name(self, grant):
        return grant.user.get_full_name() or grant.user.username


class DocumentLinkSerializer(serializers.ModelSerializer):
    display_label = serializers.SerializerMethodField()

    class Meta:
        model = DocumentLink
        fields = ["id", "document", "link_type", "student", "staff", "meeting", "fatwa", "task", "display_label", "created_at"]
        read_only_fields = ["created_at"]

    def get_display_label(self, link):
        target = link.student or link.staff or link.meeting or link.fatwa or link.task
        return str(target) if target else ""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        link_type = attrs.get("link_type")
        field_map = {"student": "student", "staff": "staff", "meeting": "meeting", "fatwa": "fatwa", "task": "task"}
        selected = [name for name in field_map.values() if attrs.get(name)]
        if selected != [field_map.get(link_type)]:
            raise serializers.ValidationError("Select exactly the relation matching the link type.")
        return attrs


class DocumentCommentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentComment
        fields = ["id", "document", "body", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["created_by", "created_at"]

    def get_created_by_name(self, comment):
        return (comment.created_by.get_full_name() or comment.created_by.username) if comment.created_by else "سسٹم"


class DocumentAcknowledgementSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAcknowledgement
        fields = ["id", "document", "user", "user_name", "acknowledged_at"]
        read_only_fields = fields

    def get_user_name(self, acknowledgement):
        return acknowledgement.user.get_full_name() or acknowledgement.user.username


class DocumentAuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentAuditEvent
        fields = ["id", "document", "action", "from_status", "to_status", "actor", "actor_name", "comment", "metadata", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, event):
        return (event.actor.get_full_name() or event.actor.username) if event.actor else "سسٹم"


class DocumentListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    folder_name = serializers.CharField(source="folder.name", read_only=True)
    owner_name = serializers.SerializerMethodField()
    current_version = serializers.SerializerMethodField()
    is_expiring = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "document_number", "title", "description", "category", "category_name", "folder", "folder_name", "status", "confidentiality", "owner", "owner_name", "reviewer", "effective_date", "expires_on", "retention_until", "keywords", "current_version_number", "current_version", "checked_out_by", "checked_out_at", "approved_at", "published_at", "created_at", "updated_at", "is_expiring"]

    def get_owner_name(self, document):
        return document.owner.get_full_name() or document.owner.username

    def get_current_version(self, document):
        version = document.versions.filter(version=document.current_version_number).first()
        return DocumentVersionSerializer(version, context=self.context).data if version else None

    def get_is_expiring(self, document):
        from django.utils import timezone
        return bool(document.expires_on and timezone.localdate() <= document.expires_on <= timezone.localdate() + timezone.timedelta(days=30))


class DocumentDetailSerializer(DocumentListSerializer):
    versions = DocumentVersionSerializer(many=True, read_only=True)
    access_grants = DocumentAccessGrantSerializer(many=True, read_only=True)
    links = DocumentLinkSerializer(many=True, read_only=True)
    comments = DocumentCommentSerializer(many=True, read_only=True)
    acknowledgements = DocumentAcknowledgementSerializer(many=True, read_only=True)
    audit_events = DocumentAuditEventSerializer(many=True, read_only=True)

    class Meta(DocumentListSerializer.Meta):
        fields = DocumentListSerializer.Meta.fields + ["versions", "access_grants", "links", "comments", "acknowledgements", "audit_events", "approved_by", "published_by", "created_by", "updated_by"]
        read_only_fields = ["document_number", "status", "current_version_number", "checked_out_by", "checked_out_at", "approved_by", "approved_at", "published_by", "published_at", "created_by", "updated_by"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status in [Document.Status.PUBLISHED, Document.Status.ARCHIVED, Document.Status.WITHDRAWN]:
            raise serializers.ValidationError("Published, archived, or withdrawn documents are locked.")
        tenant = self.context["request"].user.profile.madrasa
        for related in [attrs.get("category"), attrs.get("folder")]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        for field in ["owner", "reviewer"]:
            user = attrs.get(field)
            if user and getattr(getattr(user, "profile", None), "madrasa_id", None) != tenant.id:
                raise serializers.ValidationError({field: "User must belong to the active madrasa."})
        effective = attrs.get("effective_date", getattr(self.instance, "effective_date", None))
        expires = attrs.get("expires_on", getattr(self.instance, "expires_on", None))
        if effective and expires and expires < effective:
            raise serializers.ValidationError({"expires_on": "Expiry cannot precede effective date."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        tenant = validated_data.pop("madrasa", self.context["request"].user.profile.madrasa)
        year, number, document_number = Document.issue_number(tenant)
        return Document.objects.create(madrasa=tenant, sequence_year=year, sequence_number=number, document_number=document_number, created_by=self.context["request"].user, updated_by=self.context["request"].user, **validated_data)
