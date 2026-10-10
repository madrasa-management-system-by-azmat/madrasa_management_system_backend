from django.db import transaction
from rest_framework import serializers

from .models import FatwaAttachment, FatwaCategory, FatwaInquiry, FatwaPublication, FatwaReference, FatwaRequester, FatwaRevision, FatwaTag, FatwaWorkflowEvent


class FatwaCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FatwaCategory
        fields = ["id", "name", "code", "description", "parent", "is_active", "sort_order"]


class FatwaTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FatwaTag
        fields = ["id", "name"]


class FatwaRequesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = FatwaRequester
        fields = ["name", "guardian_or_organization", "phone", "email", "address", "country", "preferred_contact", "consent_to_contact", "consent_to_publish_question", "anonymize_on_publication", "confidential_notes"]


class FatwaRevisionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FatwaRevision
        fields = ["id", "inquiry", "version", "revision_type", "question_snapshot", "answer_text", "summary", "internal_notes", "based_on", "is_current", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["version", "question_snapshot", "is_current", "created_by", "created_at"]

    def get_created_by_name(self, revision):
        return (revision.created_by.get_full_name() or revision.created_by.username) if revision.created_by else "سسٹم"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inquiry = attrs.get("inquiry", getattr(self.instance, "inquiry", None))
        based_on = attrs.get("based_on", getattr(self.instance, "based_on", None))
        if based_on and inquiry and based_on.inquiry_id != inquiry.id:
            raise serializers.ValidationError({"based_on": "Base revision must belong to the same inquiry."})
        return attrs


class FatwaReferenceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FatwaReference
        fields = ["id", "inquiry", "revision", "reference_type", "title", "author", "volume", "page", "citation_text", "quotation", "url", "library_book", "notes", "created_by", "created_by_name", "created_at"]
        read_only_fields = ["created_by", "created_at"]

    def get_created_by_name(self, reference):
        return (reference.created_by.get_full_name() or reference.created_by.username) if reference.created_by else "سسٹم"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inquiry = attrs.get("inquiry", getattr(self.instance, "inquiry", None))
        revision = attrs.get("revision", getattr(self.instance, "revision", None))
        if revision and inquiry and revision.inquiry_id != inquiry.id:
            raise serializers.ValidationError({"revision": "Revision must belong to the same inquiry."})
        return attrs


class FatwaWorkflowEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = FatwaWorkflowEvent
        fields = ["id", "inquiry", "action", "from_status", "to_status", "actor", "actor_name", "comment", "metadata", "created_at"]
        read_only_fields = fields

    def get_actor_name(self, event):
        return (event.actor.get_full_name() or event.actor.username) if event.actor else "سسٹم"


class FatwaAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FatwaAttachment
        fields = ["id", "inquiry", "revision", "file", "original_name", "attachment_type", "visibility", "uploaded_by", "uploaded_at"]
        read_only_fields = ["original_name", "uploaded_by", "uploaded_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inquiry = attrs.get("inquiry", getattr(self.instance, "inquiry", None))
        revision = attrs.get("revision", getattr(self.instance, "revision", None))
        if revision and inquiry and revision.inquiry_id != inquiry.id:
            raise serializers.ValidationError({"revision": "Revision must belong to the same inquiry."})
        upload = attrs.get("file")
        if upload and upload.size > 10 * 1024 * 1024:
            raise serializers.ValidationError({"file": "Attachment size cannot exceed 10 MB."})
        return attrs


class FatwaPublicationSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="inquiry.category.name", read_only=True)

    class Meta:
        model = FatwaPublication
        fields = ["id", "inquiry", "revision", "public_number", "slug", "category_name", "public_question", "public_answer", "public_summary", "published_by", "published_at", "withdrawn_at", "withdrawal_reason"]
        read_only_fields = fields


class FatwaInquiryListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    mufti_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()
    current_answer = serializers.SerializerMethodField()

    class Meta:
        model = FatwaInquiry
        fields = ["id", "case_number", "subject", "category", "category_name", "language", "channel", "priority", "visibility", "status", "assigned_mufti", "mufti_name", "assigned_reviewer", "reviewer_name", "received_at", "due_at", "published_at", "public_slug", "current_answer", "updated_at"]

    def get_mufti_name(self, inquiry):
        return (inquiry.assigned_mufti.get_full_name() or inquiry.assigned_mufti.username) if inquiry.assigned_mufti else ""

    def get_reviewer_name(self, inquiry):
        return (inquiry.assigned_reviewer.get_full_name() or inquiry.assigned_reviewer.username) if inquiry.assigned_reviewer else ""

    def get_current_answer(self, inquiry):
        revision = inquiry.revisions.filter(is_current=True).first()
        return revision.answer_text if revision else ""


class FatwaInquiryDetailSerializer(FatwaInquiryListSerializer):
    requester = FatwaRequesterSerializer(required=False)
    tags = serializers.PrimaryKeyRelatedField(many=True, queryset=FatwaTag.objects.all(), required=False)
    tag_names = serializers.SerializerMethodField()
    revisions = FatwaRevisionSerializer(many=True, read_only=True)
    references = FatwaReferenceSerializer(many=True, read_only=True)
    workflow_events = FatwaWorkflowEventSerializer(many=True, read_only=True)
    attachments = FatwaAttachmentSerializer(many=True, read_only=True)
    publication = FatwaPublicationSerializer(read_only=True)

    class Meta(FatwaInquiryListSerializer.Meta):
        fields = FatwaInquiryListSerializer.Meta.fields + ["question_text", "tags", "tag_names", "requester", "revisions", "references", "workflow_events", "attachments", "publication", "created_by", "created_at"]
        read_only_fields = ["case_number", "status", "published_at", "public_slug", "created_by", "created_at"]

    def get_tag_names(self, inquiry):
        return [tag.name for tag in inquiry.tags.all()]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance and self.instance.status in [FatwaInquiry.Status.APPROVED, FatwaInquiry.Status.PUBLISHED, FatwaInquiry.Status.ARCHIVED]:
            raise serializers.ValidationError("Approved, published, or archived Fatwas are locked.")
        tenant = self.context["request"].user.profile.madrasa
        for related in [attrs.get("category"), *attrs.get("tags", [])]:
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Related records must belong to the active madrasa.")
        for field in ["assigned_mufti", "assigned_reviewer"]:
            user = attrs.get(field)
            if user and getattr(getattr(user, "profile", None), "madrasa_id", None) != tenant.id:
                raise serializers.ValidationError({field: "Assignee must belong to the active madrasa."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        requester_data = validated_data.pop("requester", {})
        tags = validated_data.pop("tags", [])
        tenant = validated_data.pop("madrasa", self.context["request"].user.profile.madrasa)
        year, number, case_number = FatwaInquiry.issue_number(tenant)
        inquiry = FatwaInquiry.objects.create(madrasa=tenant, sequence_year=year, sequence_number=number, case_number=case_number, created_by=self.context["request"].user, updated_by=self.context["request"].user, **validated_data)
        inquiry.tags.set(tags)
        FatwaRequester.objects.create(inquiry=inquiry, madrasa=tenant, **requester_data)
        FatwaWorkflowEvent.objects.create(madrasa=tenant, inquiry=inquiry, action="created", to_status=inquiry.status, actor=self.context["request"].user)
        return inquiry

    def update(self, instance, validated_data):
        requester_data = validated_data.pop("requester", None)
        tags = validated_data.pop("tags", None)
        instance = super().update(instance, validated_data)
        instance.updated_by = self.context["request"].user
        instance.save(update_fields=["updated_by", "updated_at"])
        if tags is not None:
            instance.tags.set(tags)
        if requester_data is not None:
            FatwaRequester.objects.update_or_create(inquiry=instance, defaults={"madrasa": instance.madrasa, **requester_data})
        return instance
