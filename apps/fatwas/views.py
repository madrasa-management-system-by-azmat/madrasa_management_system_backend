from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import FatwaAttachment, FatwaCategory, FatwaInquiry, FatwaPublication, FatwaReference, FatwaRevision, FatwaTag, FatwaWorkflowEvent
from .serializers import FatwaAttachmentSerializer, FatwaCategorySerializer, FatwaInquiryDetailSerializer, FatwaInquiryListSerializer, FatwaPublicationSerializer, FatwaReferenceSerializer, FatwaRevisionSerializer, FatwaTagSerializer, FatwaWorkflowEventSerializer


class FatwaViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Fatwas"])
class FatwaCategoryViewSet(FatwaViewSet):
    queryset = FatwaCategory.objects.select_related("parent")
    serializer_class = FatwaCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "name"]


@extend_schema(tags=["Fatwas"])
class FatwaTagViewSet(FatwaViewSet):
    queryset = FatwaTag.objects.all()
    serializer_class = FatwaTagSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]


@extend_schema(tags=["Fatwa Workflow"])
class FatwaInquiryViewSet(FatwaViewSet):
    queryset = FatwaInquiry.objects.select_related("category", "assigned_mufti", "assigned_reviewer", "created_by").prefetch_related("tags", "revisions", "references", "workflow_events__actor", "attachments")
    search_fields = ["case_number", "subject", "question_text", "revisions__answer_text", "category__name", "tags__name"]
    ordering_fields = ["received_at", "due_at", "priority", "status", "updated_at"]

    def get_serializer_class(self):
        return FatwaInquiryDetailSerializer if self.action in ["retrieve", "create", "update", "partial_update"] else FatwaInquiryListSerializer

    def get_queryset(self):
        queryset = super().get_queryset().distinct()
        for field in ["status", "category", "priority", "visibility", "assigned_mufti", "assigned_reviewer"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        if self.request.query_params.get("overdue") == "true":
            queryset = queryset.filter(due_at__lt=timezone.now()).exclude(status__in=[FatwaInquiry.Status.PUBLISHED, FatwaInquiry.Status.ARCHIVED, FatwaInquiry.Status.REJECTED, FatwaInquiry.Status.CANCELLED])
        return queryset

    def perform_update(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.status != FatwaInquiry.Status.RECEIVED:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only newly received inquiries can be deleted.")
        super().perform_destroy(instance)

    def _event(self, inquiry, action_name, old_status, comment="", metadata=None):
        FatwaWorkflowEvent.objects.create(madrasa=self.get_madrasa(), inquiry=inquiry, action=action_name, from_status=old_status, to_status=inquiry.status, actor=self.request.user, comment=comment, metadata=metadata or {})

    def _transition(self, inquiry, allowed, target, action_name, comment=""):
        if inquiry.status not in allowed:
            return Response({"detail": "This workflow action is not allowed in the current state."}, status=status.HTTP_400_BAD_REQUEST)
        old = inquiry.status
        inquiry.status = target
        inquiry.updated_by = self.request.user
        inquiry.save(update_fields=["status", "updated_by", "updated_at"])
        self._event(inquiry, action_name, old, comment)
        return Response(FatwaInquiryDetailSerializer(inquiry, context={"request": self.request}).data)

    @action(detail=False, methods=["get"])
    def assignees(self, request):
        from apps.users.models import UserProfile
        profiles = UserProfile.objects.filter(madrasa=self.get_madrasa(), user__is_active=True).select_related("user")
        return Response([{"id": profile.user_id, "name": profile.user.get_full_name() or profile.user.username, "role": profile.role} for profile in profiles])

    @action(detail=True, methods=["post"])
    def triage(self, request, pk=None):
        inquiry = self.get_object()
        category_id = request.data.get("category")
        if category_id:
            category = FatwaCategory.objects.filter(madrasa=self.get_madrasa(), pk=category_id).first()
            if not category:
                return Response({"category": ["Invalid category."]}, status=status.HTTP_400_BAD_REQUEST)
            inquiry.category = category
            inquiry.priority = request.data.get("priority", inquiry.priority)
            inquiry.due_at = request.data.get("due_at") or inquiry.due_at
            inquiry.save(update_fields=["category", "priority", "due_at", "updated_at"])
        return self._transition(inquiry, [FatwaInquiry.Status.RECEIVED], FatwaInquiry.Status.TRIAGED, "triaged", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        inquiry = self.get_object()
        from django.contrib.auth import get_user_model
        users = get_user_model().objects.filter(profile__madrasa=self.get_madrasa(), is_active=True)
        mufti = users.filter(pk=request.data.get("assigned_mufti")).first()
        reviewer = users.filter(pk=request.data.get("assigned_reviewer")).first()
        if not mufti:
            return Response({"assigned_mufti": ["A tenant user is required."]}, status=status.HTTP_400_BAD_REQUEST)
        inquiry.assigned_mufti = mufti
        inquiry.assigned_reviewer = reviewer
        inquiry.save(update_fields=["assigned_mufti", "assigned_reviewer", "updated_at"])
        return self._transition(inquiry, [FatwaInquiry.Status.RECEIVED, FatwaInquiry.Status.TRIAGED, FatwaInquiry.Status.ASSIGNED], FatwaInquiry.Status.ASSIGNED, "assigned", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def start_research(self, request, pk=None):
        inquiry = self.get_object()
        if request.user.profile.role != "admin" and inquiry.assigned_mufti_id != request.user.id:
            return Response({"detail": "Only the assigned Mufti can start research."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(inquiry, [FatwaInquiry.Status.ASSIGNED, FatwaInquiry.Status.CHANGES_REQUESTED], FatwaInquiry.Status.RESEARCHING, "research_started", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def start_draft(self, request, pk=None):
        inquiry = self.get_object()
        if request.user.profile.role != "admin" and inquiry.assigned_mufti_id != request.user.id:
            return Response({"detail": "Only the assigned Mufti can draft."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(inquiry, [FatwaInquiry.Status.RESEARCHING, FatwaInquiry.Status.CHANGES_REQUESTED], FatwaInquiry.Status.DRAFTING, "draft_started", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def submit_review(self, request, pk=None):
        inquiry = self.get_object()
        if request.user.profile.role != "admin" and inquiry.assigned_mufti_id != request.user.id:
            return Response({"detail": "Only the assigned Mufti can submit the draft."}, status=status.HTTP_403_FORBIDDEN)
        current = inquiry.revisions.filter(is_current=True).first()
        if not current or not current.answer_text.strip():
            return Response({"detail": "Create a complete answer draft before review."}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(inquiry, [FatwaInquiry.Status.DRAFTING], FatwaInquiry.Status.IN_REVIEW, "submitted_for_review", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    def request_changes(self, request, pk=None):
        inquiry = self.get_object()
        if request.user.profile.role != "admin" and inquiry.assigned_reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can request changes."}, status=status.HTTP_403_FORBIDDEN)
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["A reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(inquiry, [FatwaInquiry.Status.IN_REVIEW], FatwaInquiry.Status.CHANGES_REQUESTED, "changes_requested", comment)

    @action(detail=True, methods=["post"])
    def mark_reviewed(self, request, pk=None):
        inquiry = self.get_object()
        if request.user.profile.role != "admin" and inquiry.assigned_reviewer_id != request.user.id:
            return Response({"detail": "Only the assigned reviewer can complete review."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(inquiry, [FatwaInquiry.Status.IN_REVIEW], FatwaInquiry.Status.REVIEWED, "reviewed", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can approve Fatwas."}, status=status.HTTP_403_FORBIDDEN)
        inquiry = self.get_object()
        current = inquiry.revisions.filter(is_current=True).first()
        if inquiry.status != FatwaInquiry.Status.REVIEWED or not current or not current.answer_text.strip():
            return Response({"detail": "A reviewed answer is required before approval."}, status=status.HTTP_400_BAD_REQUEST)
        current.revision_type = FatwaRevision.RevisionType.APPROVED
        current.save(update_fields=["revision_type"])
        return self._transition(inquiry, [FatwaInquiry.Status.REVIEWED], FatwaInquiry.Status.APPROVED, "approved", request.data.get("comment", ""))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def publish(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can publish Fatwas."}, status=status.HTTP_403_FORBIDDEN)
        inquiry = self.get_object()
        if inquiry.status != FatwaInquiry.Status.APPROVED:
            return Response({"detail": "Approve the Fatwa before publication."}, status=status.HTTP_400_BAD_REQUEST)
        requester = getattr(inquiry, "requester", None)
        if requester and not requester.consent_to_publish_question:
            return Response({"detail": "Requester publication consent is required."}, status=status.HTTP_400_BAD_REQUEST)
        revision = inquiry.revisions.filter(is_current=True, revision_type=FatwaRevision.RevisionType.APPROVED).first()
        if not revision:
            return Response({"detail": "Approved revision not found."}, status=status.HTTP_400_BAD_REQUEST)
        base_slug = slugify(request.data.get("slug") or inquiry.subject, allow_unicode=True) or inquiry.case_number.lower()
        slug = base_slug
        counter = 2
        while FatwaPublication.objects.filter(madrasa=self.get_madrasa(), slug=slug).exclude(inquiry=inquiry).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        publication, _ = FatwaPublication.objects.update_or_create(inquiry=inquiry, defaults={"madrasa": self.get_madrasa(), "revision": revision, "public_number": inquiry.case_number, "slug": slug, "public_question": request.data.get("public_question") or revision.question_snapshot, "public_answer": request.data.get("public_answer") or revision.answer_text, "public_summary": request.data.get("public_summary") or revision.summary, "published_by": request.user, "published_at": timezone.now(), "withdrawn_at": None, "withdrawal_reason": ""})
        old = inquiry.status
        inquiry.status = FatwaInquiry.Status.PUBLISHED
        inquiry.visibility = FatwaInquiry.Visibility.PUBLIC
        inquiry.public_slug = publication.slug
        inquiry.published_at = publication.published_at
        inquiry.published_by = request.user
        inquiry.save(update_fields=["status", "visibility", "public_slug", "published_at", "published_by", "updated_at"])
        self._event(inquiry, "published", old, request.data.get("comment", ""))
        return Response(FatwaPublicationSerializer(publication).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can archive Fatwas."}, status=status.HTTP_403_FORBIDDEN)
        return self._transition(self.get_object(), [FatwaInquiry.Status.PUBLISHED, FatwaInquiry.Status.REJECTED, FatwaInquiry.Status.CANCELLED], FatwaInquiry.Status.ARCHIVED, "archived", request.data.get("comment", ""))

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        return Response(FatwaWorkflowEventSerializer(self.get_object().workflow_events.select_related("actor"), many=True).data)


@extend_schema(tags=["Fatwa Workflow"])
class FatwaRevisionViewSet(FatwaViewSet):
    queryset = FatwaRevision.objects.select_related("inquiry", "created_by")
    serializer_class = FatwaRevisionSerializer
    search_fields = ["inquiry__case_number", "inquiry__subject", "answer_text", "summary"]
    ordering_fields = ["created_at", "version"]

    @transaction.atomic
    def perform_create(self, serializer):
        inquiry = serializer.validated_data["inquiry"]
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        if self.request.user.profile.role != "admin" and inquiry.assigned_mufti_id != self.request.user.id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the assigned Mufti can create revisions.")
        if inquiry.status in [FatwaInquiry.Status.APPROVED, FatwaInquiry.Status.PUBLISHED, FatwaInquiry.Status.ARCHIVED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Approved, published, or archived Fatwas are locked.")
        latest = inquiry.revisions.select_for_update().order_by("-version").first()
        inquiry.revisions.update(is_current=False)
        revision = serializer.save(madrasa=self.get_madrasa(), version=(latest.version + 1 if latest else 1), question_snapshot=inquiry.question_text, is_current=True, created_by=self.request.user)
        FatwaWorkflowEvent.objects.create(madrasa=self.get_madrasa(), inquiry=inquiry, action="revision_created", from_status=inquiry.status, to_status=inquiry.status, actor=self.request.user, metadata={"revision": revision.id, "version": revision.version})

    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Fatwa revisions are immutable; create a new revision.")

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        raise ValidationError("Fatwa revisions cannot be deleted.")


@extend_schema(tags=["Fatwa Workflow"])
class FatwaReferenceViewSet(FatwaViewSet):
    queryset = FatwaReference.objects.select_related("inquiry", "revision", "library_book", "created_by")
    serializer_class = FatwaReferenceSerializer
    search_fields = ["inquiry__case_number", "title", "author", "citation_text", "quotation"]
    ordering_fields = ["created_at", "id"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Fatwa Workflow"])
class FatwaAttachmentViewSet(FatwaViewSet):
    queryset = FatwaAttachment.objects.select_related("inquiry", "revision", "uploaded_by")
    serializer_class = FatwaAttachmentSerializer

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        upload = serializer.validated_data["file"]
        serializer.save(madrasa=self.get_madrasa(), original_name=upload.name, uploaded_by=self.request.user)


@extend_schema(tags=["Fatwas"])
class FatwaPublicationViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = FatwaPublication.objects.filter(withdrawn_at__isnull=True).select_related("inquiry__category", "revision")
    serializer_class = FatwaPublicationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["public_number", "public_question", "public_answer", "public_summary", "inquiry__category__name"]
    ordering_fields = ["published_at", "public_number"]


class FatwaDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = FatwaInquiry.objects.none()

    def list(self, request):
        tenant = self.get_madrasa()
        rows = FatwaInquiry.objects.filter(madrasa=tenant)
        now = timezone.now()
        active_statuses = [FatwaInquiry.Status.RECEIVED, FatwaInquiry.Status.TRIAGED, FatwaInquiry.Status.ASSIGNED, FatwaInquiry.Status.RESEARCHING, FatwaInquiry.Status.DRAFTING, FatwaInquiry.Status.IN_REVIEW, FatwaInquiry.Status.CHANGES_REQUESTED, FatwaInquiry.Status.REVIEWED, FatwaInquiry.Status.APPROVED]
        categories = rows.values("category__name").annotate(count=Count("id")).order_by("-count")[:6]
        return Response({
            "total": rows.count(),
            "received": rows.filter(status=FatwaInquiry.Status.RECEIVED).count(),
            "active": rows.filter(status__in=active_statuses).count(),
            "in_review": rows.filter(status=FatwaInquiry.Status.IN_REVIEW).count(),
            "awaiting_approval": rows.filter(status=FatwaInquiry.Status.REVIEWED).count(),
            "overdue": rows.filter(status__in=active_statuses, due_at__lt=now).count(),
            "published": rows.filter(status=FatwaInquiry.Status.PUBLISHED).count(),
            "published_this_month": rows.filter(status=FatwaInquiry.Status.PUBLISHED, published_at__year=now.year, published_at__month=now.month).count(),
            "categories": list(categories),
            "recent": FatwaInquiryListSerializer(rows[:10], many=True).data,
        })
