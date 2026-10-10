from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.tenancy import TenantScopedViewSetMixin
from .models import Certificate, CertificateEvent, CertificateVerificationLog
from .serializers import CertificateSerializer
from .services import sign_certificate, verify_signature


class CertificateViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Certificate.objects.select_related("student", "staff", "alumni__student", "madrasa__profile").prefetch_related("events__actor")
    serializer_class = CertificateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["serial_number", "recipient_name_snapshot", "recipient_identifier_snapshot", "title"]
    ordering_fields = ["created_at", "issued_on", "status", "certificate_type"]

    def get_queryset(self):
        queryset = super().get_queryset()
        source_fingerprint = self.request.query_params.get("source_fingerprint")
        certificate_status = self.request.query_params.get("status")
        if source_fingerprint:
            queryset = queryset.filter(source_fingerprint=source_fingerprint)
        if certificate_status:
            queryset = queryset.filter(status=certificate_status)
        return queryset

    def perform_create(self, serializer):
        if self.request.user.profile.role not in ["admin", "operator"]:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Certificate management access is required.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Certificate.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft certificates can be deleted.")
        super().perform_destroy(instance)

    def _event(self, certificate, action_name, old, reason=""):
        CertificateEvent.objects.create(madrasa=self.get_madrasa(), certificate=certificate, action=action_name, from_status=old, to_status=certificate.status, actor=self.request.user, reason=reason)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can approve certificates."}, status=403)
        certificate = self.get_object()
        if certificate.status != Certificate.Status.DRAFT:
            return Response({"detail": "Only draft certificates can be approved."}, status=400)
        old = certificate.status
        certificate.status = Certificate.Status.APPROVED
        certificate.approved_by = request.user
        certificate.approved_at = timezone.now()
        certificate.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        self._event(certificate, "approved", old)
        return Response(self.get_serializer(certificate).data)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can issue certificates."}, status=403)
        certificate = self.get_object()
        if certificate.status != Certificate.Status.APPROVED:
            return Response({"detail": "Approve the certificate before issuance."}, status=400)
        old = certificate.status
        certificate.status = Certificate.Status.ISSUED
        certificate.issued_on = request.data.get("issued_on") or timezone.localdate()
        certificate.issued_by = request.user
        certificate.issued_at = timezone.now()
        sign_certificate(certificate)
        certificate.save(update_fields=["status", "issued_on", "issued_by", "issued_at", "payload_hash", "signature", "updated_at"])
        self._event(certificate, "issued", old)
        return Response(self.get_serializer(certificate).data)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can revoke certificates."}, status=403)
        certificate = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if certificate.status != Certificate.Status.ISSUED or not reason:
            return Response({"detail": "An issued certificate and revocation reason are required."}, status=400)
        old = certificate.status
        certificate.status = Certificate.Status.REVOKED
        certificate.revoked_by = request.user
        certificate.revoked_at = timezone.now()
        certificate.revocation_reason = reason
        certificate.save(update_fields=["status", "revoked_by", "revoked_at", "revocation_reason", "updated_at"])
        self._event(certificate, "revoked", old, reason)
        return Response(self.get_serializer(certificate).data)

    @action(detail=True, methods=["post"])
    def reissue(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can reissue certificates."}, status=403)
        original = self.get_object()
        if original.status not in [Certificate.Status.ISSUED, Certificate.Status.REVOKED]:
            return Response({"detail": "Only issued or revoked certificates can be reissued."}, status=400)
        clone = Certificate.objects.create(madrasa=original.madrasa, serial_number=Certificate.issue_serial(original.madrasa, original.certificate_type), certificate_type=original.certificate_type, recipient_kind=original.recipient_kind, student=original.student, staff=original.staff, alumni=original.alumni, recipient_name_snapshot=request.data.get("recipient_name") or original.recipient_name_snapshot, recipient_identifier_snapshot=original.recipient_identifier_snapshot, title=request.data.get("title") or original.title, body_snapshot=request.data.get("body") or original.body_snapshot, issuer_snapshot=original.issuer_snapshot, credential_snapshot=original.credential_snapshot, source_type=original.source_type, source_object_id=original.source_object_id, source_fingerprint="", supersedes=original, revision_number=original.revision_number + 1, created_by=request.user)
        old = original.status
        original.status = Certificate.Status.SUPERSEDED
        original.save(update_fields=["status", "updated_at"])
        self._event(original, "superseded", old, request.data.get("reason", "Reissued"))
        CertificateEvent.objects.create(madrasa=clone.madrasa, certificate=clone, action="reissued", to_status=clone.status, actor=request.user, metadata={"supersedes": original.id})
        return Response(self.get_serializer(clone).data, status=201)


class PublicCertificateVerificationAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id):
        certificate = Certificate.objects.filter(public_id=public_id).select_related("madrasa__profile").first()
        if not certificate:
            return Response({"valid": False, "status": "invalid", "detail": "Certificate not found."}, status=404)
        valid_signature = verify_signature(certificate) if certificate.signature else False
        result = "valid" if certificate.status == Certificate.Status.ISSUED and valid_signature else "revoked" if certificate.status in [Certificate.Status.REVOKED, Certificate.Status.SUPERSEDED] else "invalid"
        CertificateVerificationLog.objects.create(certificate=certificate, madrasa=certificate.madrasa, result=result, ip_address=request.META.get("REMOTE_ADDR"), user_agent=request.META.get("HTTP_USER_AGENT", "")[:300])
        return Response({"valid": result == "valid", "status": result, "serial_number": certificate.serial_number, "certificate_type": certificate.certificate_type, "title": certificate.title, "recipient_name": certificate.recipient_name_snapshot, "recipient_identifier": certificate.recipient_identifier_snapshot, "issued_on": certificate.issued_on, "issuer": {key: certificate.issuer_snapshot.get(key, "") for key in ["name", "name_english", "registration_number", "city"]}, "credential": certificate.credential_snapshot, "revision": certificate.revision_number, "revocation_reason": certificate.revocation_reason if result == "revoked" else "", "verified_at": timezone.now()})


class CertificateDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = Certificate.objects.none()
    def list(self, request):
        rows = Certificate.objects.filter(madrasa=self.get_madrasa())
        return Response({"total": rows.count(), "draft": rows.filter(status="draft").count(), "approved": rows.filter(status="approved").count(), "issued": rows.filter(status="issued").count(), "revoked": rows.filter(status="revoked").count(), "verifications": CertificateVerificationLog.objects.filter(madrasa=self.get_madrasa()).count(), "recent": CertificateSerializer(rows[:10], many=True, context={"request": request}).data})
