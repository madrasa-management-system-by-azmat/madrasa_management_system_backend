from django.utils import timezone
from rest_framework import serializers

from .models import Certificate, CertificateEvent, CertificateTemplate


class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "code",
            "title",
            "arabic_title",
            "subtitle",
            "body_text_male",
            "body_text_female",
            "grade",
            "dua",
            "signatures",
            "curriculum_books",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CertificateEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    class Meta:
        model = CertificateEvent
        fields = ["id", "action", "from_status", "to_status", "actor", "actor_name", "reason", "metadata", "created_at"]
        read_only_fields = fields
    def get_actor_name(self, event):
        return (event.actor.get_full_name() or event.actor.username) if event.actor else "سسٹم"


class CertificateSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source="recipient_name_snapshot", read_only=True)
    verification_url = serializers.SerializerMethodField()
    events = CertificateEventSerializer(many=True, read_only=True)

    class Meta:
        model = Certificate
        fields = ["id", "public_id", "serial_number", "certificate_type", "recipient_kind", "student", "staff", "alumni", "recipient_name", "recipient_name_snapshot", "recipient_identifier_snapshot", "title", "body_snapshot", "issuer_snapshot", "credential_snapshot", "source_type", "source_object_id", "source_fingerprint", "status", "issued_on", "approved_by", "approved_at", "issued_by", "issued_at", "revoked_by", "revoked_at", "revocation_reason", "supersedes", "revision_number", "payload_hash", "signature", "verification_url", "created_by", "created_at", "updated_at", "events"]
        read_only_fields = ["public_id", "serial_number", "status", "issuer_snapshot", "approved_by", "approved_at", "issued_by", "issued_at", "revoked_by", "revoked_at", "revocation_reason", "revision_number", "payload_hash", "signature", "created_by", "created_at", "updated_at"]

    def get_verification_url(self, certificate):
        request = self.context.get("request")
        path = f"/verify/certificate/{certificate.public_id}"
        if request:
            frontend = request.headers.get("Origin") or "http://127.0.0.1:3000"
            return f"{frontend}{path}"
        return path

    def validate(self, attrs):
        attrs = super().validate(attrs)
        kind = attrs.get("recipient_kind", getattr(self.instance, "recipient_kind", None))
        relations = {"student": attrs.get("student", getattr(self.instance, "student", None)), "staff": attrs.get("staff", getattr(self.instance, "staff", None)), "alumni": attrs.get("alumni", getattr(self.instance, "alumni", None))}
        selected = [key for key, value in relations.items() if value]
        if kind == "external" and selected:
            raise serializers.ValidationError("External recipients cannot have managed recipient relations.")
        if kind != "external" and selected != [kind]:
            raise serializers.ValidationError("Select exactly the relation matching recipient kind.")
        tenant = self.context["request"].user.profile.madrasa
        for related in relations.values():
            if related and related.madrasa_id != tenant.id:
                raise serializers.ValidationError("Recipient must belong to the active madrasa.")
        if self.instance and self.instance.status in [Certificate.Status.ISSUED, Certificate.Status.REVOKED, Certificate.Status.SUPERSEDED]:
            raise serializers.ValidationError("Issued or closed certificates are immutable.")
        return attrs

    def create(self, validated_data):
        tenant = self.context["request"].user.profile.madrasa
        profile = getattr(tenant, "profile", None)
        issuer = {"name": getattr(profile, "name", "") or tenant.name, "name_english": getattr(profile, "name_english", ""), "registration_number": getattr(profile, "registration_number", ""), "address": getattr(profile, "address", ""), "city": getattr(profile, "city", ""), "phone": getattr(profile, "phone", ""), "principal_name": getattr(profile, "principal_name", ""), "principal_title": getattr(profile, "principal_title", ""), "primary_color": getattr(profile, "primary_color", "#226CE0"), "sidebar_color": getattr(profile, "sidebar_color", "#172554")}
        certificate = Certificate.objects.create(madrasa=tenant, serial_number=Certificate.issue_serial(tenant, validated_data["certificate_type"]), issuer_snapshot=issuer, created_by=self.context["request"].user, **validated_data)
        CertificateEvent.objects.create(madrasa=tenant, certificate=certificate, action="created", to_status=certificate.status, actor=self.context["request"].user)
        return certificate
