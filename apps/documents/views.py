import hashlib
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import Document, DocumentAccessGrant, DocumentAcknowledgement, DocumentAuditEvent, DocumentCategory, DocumentComment, DocumentFolder, DocumentLink, DocumentVersion
from .serializers import DocumentAccessGrantSerializer, DocumentAcknowledgementSerializer, DocumentCategorySerializer, DocumentCommentSerializer, DocumentDetailSerializer, DocumentFolderSerializer, DocumentLinkSerializer, DocumentListSerializer, DocumentVersionSerializer


class DocumentBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


def can_access_document(user, document, permission="view"):
    profile = getattr(user, "profile", None)
    if not profile or profile.madrasa_id != document.madrasa_id:
        return False
    if profile.role == "admin" or document.owner_id == user.id or document.reviewer_id == user.id:
        return True
    grant = document.access_grants.filter(user=user).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
    if grant:
        hierarchy = {"view": 1, "edit": 2, "approve": 3, "manage": 4}
        return hierarchy[grant.permission] >= hierarchy[permission]
    return document.confidentiality in [Document.Confidentiality.INTERNAL, Document.Confidentiality.PUBLIC] and permission == "view"


@extend_schema(tags=["Documents"])
class DocumentCategoryViewSet(DocumentBaseViewSet):
    queryset = DocumentCategory.objects.select_related("parent")
    serializer_class = DocumentCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "name"]


@extend_schema(tags=["Documents"])
class DocumentFolderViewSet(DocumentBaseViewSet):
    queryset = DocumentFolder.objects.select_related("parent", "created_by")
    serializer_class = DocumentFolderSerializer
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Documents"])
class DocumentViewSet(DocumentBaseViewSet):
    queryset = Document.objects.select_related("category", "folder", "owner", "reviewer", "approved_by", "published_by").prefetch_related("versions", "access_grants__user", "links", "comments__created_by", "acknowledgements__user", "audit_events__actor")
    search_fields = ["document_number", "title", "description", "keywords", "category__name", "versions__original_name"]
    ordering_fields = ["updated_at", "created_at", "expires_on", "status", "title"]

    def get_serializer_class(self):
        return DocumentDetailSerializer if self.action in ["retrieve", "create", "update", "partial_update"] else DocumentListSerializer

    def get_queryset(self):
        queryset = super().get_queryset().distinct()
        profile = self.request.user.profile
        if profile.role != "admin":
            queryset = queryset.filter(Q(owner=self.request.user) | Q(reviewer=self.request.user) | Q(access_grants__user=self.request.user, access_grants__expires_at__isnull=True) | Q(access_grants__user=self.request.user, access_grants__expires_at__gt=timezone.now()) | Q(confidentiality__in=[Document.Confidentiality.INTERNAL, Document.Confidentiality.PUBLIC])).distinct()
        for field in ["status", "category", "folder", "confidentiality", "owner"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        if self.request.query_params.get("expiring") == "true":
            queryset = queryset.filter(expires_on__range=[timezone.localdate(), timezone.localdate() + timedelta(days=30)])
        return queryset

    def perform_update(self, serializer):
        if not can_access_document(self.request.user, serializer.instance, "edit"):
            raise PermissionDenied("Edit access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.status != Document.Status.DRAFT or instance.versions.exists():
            raise ValidationError("Only empty draft documents can be deleted.")
        if not can_access_document(self.request.user, instance, "manage"):
            raise PermissionDenied("Manage access is required.")
        super().perform_destroy(instance)

    def _event(self, document, action_name, old_status, comment="", metadata=None):
        DocumentAuditEvent.objects.create(madrasa=self.get_madrasa(), document=document, action=action_name, from_status=old_status, to_status=document.status, actor=self.request.user, comment=comment, metadata=metadata or {})

    def _transition(self, document, allowed, target, action_name, comment="", fields=None):
        if document.status not in allowed:
            return Response({"detail": "This workflow action is not allowed in the current state."}, status=status.HTTP_400_BAD_REQUEST)
        old = document.status
        document.status = target
        document.updated_by = self.request.user
        update_fields = ["status", "updated_by", "updated_at"]
        for key, value in (fields or {}).items():
            setattr(document, key, value)
            update_fields.append(key)
        document.save(update_fields=update_fields)
        self._event(document, action_name, old, comment)
        return Response(DocumentDetailSerializer(document, context={"request": self.request}).data)

    @action(detail=False, methods=["get"])
    def people_lookup(self, request):
        from apps.users.models import UserProfile
        profiles = UserProfile.objects.filter(madrasa=self.get_madrasa(), user__is_active=True).select_related("user")
        return Response([{"id": item.user_id, "name": item.user.get_full_name() or item.user.username, "role": item.role} for item in profiles])

    @action(detail=True, methods=["post"])
    def checkout(self, request, pk=None):
        document = self.get_object()
        if not can_access_document(request.user, document, "edit"):
            return Response({"detail": "Edit access is required."}, status=status.HTTP_403_FORBIDDEN)
        if document.checked_out_by_id and document.checked_out_by_id != request.user.id:
            return Response({"detail": "Document is checked out by another user."}, status=status.HTTP_409_CONFLICT)
        document.checked_out_by = request.user
        document.checked_out_at = timezone.now()
        document.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
        self._event(document, "checked_out", document.status)
        return Response(DocumentDetailSerializer(document, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def checkin(self, request, pk=None):
        document = self.get_object()
        if document.checked_out_by_id not in [None, request.user.id] and request.user.profile.role != "admin":
            return Response({"detail": "Only the current editor or an administrator can check in."}, status=status.HTTP_403_FORBIDDEN)
        document.checked_out_by = None
        document.checked_out_at = None
        document.save(update_fields=["checked_out_by", "checked_out_at", "updated_at"])
        self._event(document, "checked_in", document.status)
        return Response(DocumentDetailSerializer(document, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def submit_review(self, request, pk=None):
        document = self.get_object()
        if not document.versions.exists():
            return Response({"detail": "Upload at least one document version first."}, status=status.HTTP_400_BAD_REQUEST)
        if not document.reviewer_id:
            return Response({"detail": "Assign a reviewer first."}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(document, [Document.Status.DRAFT, Document.Status.CHANGES_REQUESTED], Document.Status.IN_REVIEW, "submitted_for_review", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def request_changes(self, request, pk=None):
        document = self.get_object()
        if request.user.profile.role != "admin" and document.reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can request changes."}, status=status.HTTP_403_FORBIDDEN)
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["A reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(document, [Document.Status.IN_REVIEW], Document.Status.CHANGES_REQUESTED, "changes_requested", comment)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        document = self.get_object()
        if request.user.profile.role != "admin" and document.reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can approve this document."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(document, [Document.Status.IN_REVIEW], Document.Status.APPROVED, "approved", request.data.get("comment", ""), {"approved_by": request.user, "approved_at": timezone.now(), "checked_out_by": None, "checked_out_at": None})

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can publish documents."}, status=status.HTTP_403_FORBIDDEN)
        document = self.get_object()
        return self._transition(document, [Document.Status.APPROVED], Document.Status.PUBLISHED, "published", request.data.get("comment", ""), {"confidentiality": Document.Confidentiality.PUBLIC, "published_by": request.user, "published_at": timezone.now()})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can archive documents."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(self.get_object(), [Document.Status.APPROVED, Document.Status.PUBLISHED, Document.Status.EXPIRED, Document.Status.WITHDRAWN], Document.Status.ARCHIVED, "archived", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        document = self.get_object()
        if not can_access_document(request.user, document):
            return Response({"detail": "Document access is required."}, status=status.HTTP_403_FORBIDDEN)
        acknowledgement, _ = DocumentAcknowledgement.objects.get_or_create(madrasa=self.get_madrasa(), document=document, user=request.user)
        return Response(DocumentAcknowledgementSerializer(acknowledgement).data)


@extend_schema(tags=["Documents"])
class DocumentVersionViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = DocumentVersion.objects.select_related("document", "uploaded_by")
    serializer_class = DocumentVersionSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "admin":
            return queryset
        return queryset.filter(Q(document__owner=self.request.user) | Q(document__reviewer=self.request.user) | Q(document__access_grants__user=self.request.user) | Q(document__confidentiality__in=[Document.Confidentiality.INTERNAL, Document.Confidentiality.PUBLIC])).distinct()

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def upload(self, request):
        document = Document.objects.filter(madrasa=self.get_madrasa(), pk=request.data.get("document")).first()
        if not document:
            return Response({"document": ["Document not found."]}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_document(request.user, document, "edit"):
            return Response({"detail": "Edit access is required."}, status=status.HTTP_403_FORBIDDEN)
        if document.status in [Document.Status.APPROVED, Document.Status.PUBLISHED, Document.Status.ARCHIVED, Document.Status.WITHDRAWN]:
            return Response({"detail": "Approved or closed documents cannot receive new versions."}, status=status.HTTP_400_BAD_REQUEST)
        if document.checked_out_by_id and document.checked_out_by_id != request.user.id:
            return Response({"detail": "Document is checked out by another user."}, status=status.HTTP_409_CONFLICT)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"file": ["A file is required."]}, status=status.HTTP_400_BAD_REQUEST)
        extension = Path(upload.name).suffix.lower().lstrip(".")
        allowed = {item.strip().lower() for item in document.category.allowed_extensions.split(",") if item.strip()}
        if extension not in allowed:
            return Response({"file": ["This file type is not allowed for the category."]}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > document.category.maximum_size_bytes:
            return Response({"file": ["File exceeds the category size limit."]}, status=status.HTTP_400_BAD_REQUEST)
        digest = hashlib.sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(0)
        version_number = document.current_version_number + 1
        version = DocumentVersion.objects.create(madrasa=self.get_madrasa(), document=document, version=version_number, file=upload, original_name=upload.name, content_type=getattr(upload, "content_type", "") or mimetypes.guess_type(upload.name)[0] or "application/octet-stream", size_bytes=upload.size, checksum_sha256=digest.hexdigest(), change_summary=request.data.get("change_summary", ""), uploaded_by=request.user)
        document.current_version_number = version_number
        document.checked_out_by = None
        document.checked_out_at = None
        document.updated_by = request.user
        document.save(update_fields=["current_version_number", "checked_out_by", "checked_out_at", "updated_by", "updated_at"])
        DocumentAuditEvent.objects.create(madrasa=self.get_madrasa(), document=document, action="version_uploaded", from_status=document.status, to_status=document.status, actor=request.user, metadata={"version": version_number, "checksum": version.checksum_sha256})
        return Response(DocumentVersionSerializer(version, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        version = self.get_object()
        if not can_access_document(request.user, version.document):
            raise PermissionDenied("Document access is required.")
        DocumentAuditEvent.objects.create(madrasa=self.get_madrasa(), document=version.document, action="downloaded", from_status=version.document.status, to_status=version.document.status, actor=request.user, metadata={"version": version.version})
        response = FileResponse(version.file.open("rb"), as_attachment=True, filename=version.original_name, content_type=version.content_type or "application/octet-stream")
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


@extend_schema(tags=["Documents"])
class DocumentAccessGrantViewSet(DocumentBaseViewSet):
    queryset = DocumentAccessGrant.objects.select_related("document", "user", "granted_by")
    serializer_class = DocumentAccessGrantSerializer

    def perform_create(self, serializer):
        document = serializer.validated_data["document"]
        if not can_access_document(self.request.user, document, "manage"):
            raise PermissionDenied("Manage access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), granted_by=self.request.user)


@extend_schema(tags=["Documents"])
class DocumentLinkViewSet(DocumentBaseViewSet):
    queryset = DocumentLink.objects.select_related("document", "student", "staff", "meeting", "fatwa", "task")
    serializer_class = DocumentLinkSerializer

    def perform_create(self, serializer):
        if not can_access_document(self.request.user, serializer.validated_data["document"], "edit"):
            raise PermissionDenied("Edit access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa())


@extend_schema(tags=["Documents"])
class DocumentCommentViewSet(DocumentBaseViewSet):
    queryset = DocumentComment.objects.select_related("document", "created_by")
    serializer_class = DocumentCommentSerializer

    def perform_create(self, serializer):
        if not can_access_document(self.request.user, serializer.validated_data["document"]):
            raise PermissionDenied("Document access is required.")
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


class DocumentDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = Document.objects.none()

    def list(self, request):
        queryset = Document.objects.filter(madrasa=self.get_madrasa())
        if request.user.profile.role != "admin":
            queryset = queryset.filter(Q(owner=request.user) | Q(reviewer=request.user) | Q(access_grants__user=request.user) | Q(confidentiality__in=[Document.Confidentiality.INTERNAL, Document.Confidentiality.PUBLIC])).distinct()
        today = timezone.localdate()
        Document.objects.filter(madrasa=self.get_madrasa(), expires_on__lt=today, status__in=[Document.Status.APPROVED, Document.Status.PUBLISHED]).update(status=Document.Status.EXPIRED)
        total_size = DocumentVersion.objects.filter(madrasa=self.get_madrasa()).aggregate(value=Sum("size_bytes"))["value"] or 0
        return Response({
            "total": queryset.count(),
            "draft": queryset.filter(status=Document.Status.DRAFT).count(),
            "in_review": queryset.filter(status=Document.Status.IN_REVIEW).count(),
            "approved": queryset.filter(status=Document.Status.APPROVED).count(),
            "published": queryset.filter(status=Document.Status.PUBLISHED).count(),
            "expiring": queryset.filter(expires_on__range=[today, today + timedelta(days=30)]).count(),
            "expired": queryset.filter(status=Document.Status.EXPIRED).count(),
            "storage_bytes": total_size,
            "categories": list(queryset.values("category__name").annotate(count=Count("id")).order_by("-count")[:6]),
            "recent": DocumentListSerializer(queryset[:10], many=True, context={"request": request}).data,
        })
