from django.db.models import Count
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import DutyAssignment, DutyCategory, GuestInvitation, Taqreeb
from .serializers import (
    DutyAssignmentSerializer,
    DutyCategorySerializer,
    GuestInvitationSerializer,
    TaqreebDetailSerializer,
    TaqreebListSerializer,
)

DEFAULT_DUTY_CATEGORIES = [
    {"name": "استقبال مہمانان", "code": "reception", "color": "#0d9488", "description": "مہمانوں کا خیرمقدم اور پروٹوکول"},
    {"name": "انتظام طعام و ضیافت", "code": "dining", "color": "#d97706", "description": "کھانے پینے اور مہمان نوازی کا انتظام"},
    {"name": "نظم و ضبط طلبہ", "code": "discipline", "color": "#b91c1c", "description": "طلبہ کی نگرانی اور پنڈال کا امن و امان"},
    {"name": "انتظام اسٹیج و نظامت", "code": "stage", "color": "#4338ca", "description": "اسٹیج کا اہتمام، نشستیں اور نظامت"},
    {"name": "ساؤنڈ سسٹم و ریکارڈنگ", "code": "media", "color": "#0284c7", "description": "مائیک، آواز، کیمرہ اور ریکارڈنگ"},
    {"name": "تقسیم اسناد و انعامات", "code": "awards", "color": "#7c3aed", "description": "اسناد، شیلڈز اور انعامات کی فراہمی"},
    {"name": "صفائی و ستھرائی", "code": "cleaning", "color": "#15803d", "description": "پنڈال، ہال اور احاطہ کی صفائی"},
    {"name": "رہائش و ہاسٹل انتظام", "code": "lodging", "color": "#c2410c", "description": "بیرونی مہمانوں کے قیام و آرام کا انتظام"},
    {"name": "سیکیورٹی و پارکنگ", "code": "security", "color": "#374151", "description": "گاڑیوں کی پارکنگ اور داخلی راستوں کی سیکیورٹی"},
]


class TaqreebBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Taqreeb"])
class TaqreebViewSet(TaqreebBaseViewSet):
    queryset = Taqreeb.objects.annotate(
        duties_count=Count("duties", distinct=True),
        invitations_count=Count("invitations", distinct=True),
    )
    search_fields = ["title", "venue", "chief_guest", "president", "description"]
    ordering_fields = ["event_date", "created_at", "status", "title"]

    def get_serializer_class(self):
        if self.action in ["retrieve", "create", "update", "partial_update"]:
            return TaqreebDetailSerializer
        return TaqreebListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        event_type = self.request.query_params.get("event_type")
        upcoming = self.request.query_params.get("upcoming")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if upcoming == "true":
            queryset = queryset.filter(event_date__gte=timezone.now().date())

        return queryset

    def perform_create(self, serializer):
        tenant = self.get_madrasa()
        serializer.save(madrasa=tenant, created_by=self.request.user)

    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        tenant = self.get_madrasa()
        today = timezone.now().date()
        total_events = Taqreeb.objects.filter(madrasa=tenant).count()
        upcoming_events = Taqreeb.objects.filter(madrasa=tenant, event_date__gte=today).count()
        completed_events = Taqreeb.objects.filter(madrasa=tenant, status=Taqreeb.Status.COMPLETED).count()
        total_duties = DutyAssignment.objects.filter(madrasa=tenant).count()
        total_invitations = GuestInvitation.objects.filter(madrasa=tenant).count()

        return Response({
            "total_events": total_events,
            "upcoming_events": upcoming_events,
            "completed_events": completed_events,
            "total_duties": total_duties,
            "total_invitations": total_invitations,
        })

    @action(detail=False, methods=["post"], url_path="seed-categories")
    def seed_categories(self, request):
        tenant = self.get_madrasa()
        created_count = 0
        for idx, item in enumerate(DEFAULT_DUTY_CATEGORIES):
            _, created = DutyCategory.objects.get_or_create(
                madrasa=tenant,
                name=item["name"],
                defaults={
                    "code": item["code"],
                    "color": item["color"],
                    "description": item["description"],
                    "sort_order": idx,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1

        return Response({
            "status": "ok",
            "message": f"{created_count} نئے شعبہ جات شامل کر دیے گئے۔",
            "created_count": created_count,
        })


@extend_schema(tags=["Taqreeb"])
class DutyCategoryViewSet(TaqreebBaseViewSet):
    queryset = DutyCategory.objects.annotate(
        duties_count=Count("assignments", distinct=True)
    )
    serializer_class = DutyCategorySerializer
    search_fields = ["name", "code", "description"]
    ordering_fields = ["sort_order", "name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        active = self.request.query_params.get("is_active")
        if active in ["true", "1"]:
            queryset = queryset.filter(is_active=True)
        return queryset


@extend_schema(tags=["Taqreeb"])
class DutyAssignmentViewSet(TaqreebBaseViewSet):
    queryset = DutyAssignment.objects.select_related(
        "taqreeb", "duty_category", "student", "staff"
    ).prefetch_related("student__enrollments__academic_class")
    serializer_class = DutyAssignmentSerializer
    search_fields = [
        "duty_title",
        "location",
        "card_number",
        "student__full_name",
        "student__registration_number",
        "staff__full_name",
    ]
    ordering_fields = ["id", "created_at", "status", "duty_title"]

    def get_queryset(self):
        queryset = super().get_queryset()
        taqreeb_id = self.request.query_params.get("taqreeb")
        category_id = self.request.query_params.get("duty_category")
        assignee_type = self.request.query_params.get("assignee_type")
        status_filter = self.request.query_params.get("status")

        if taqreeb_id:
            queryset = queryset.filter(taqreeb_id=taqreeb_id)
        if category_id:
            queryset = queryset.filter(duty_category_id=category_id)
        if assignee_type:
            queryset = queryset.filter(assignee_type=assignee_type)
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        return queryset

    @action(detail=False, methods=["post"], url_path="bulk-assign")
    def bulk_assign(self, request):
        tenant = self.get_madrasa()
        data = request.data
        taqreeb_id = data.get("taqreeb")
        assignee_type = data.get("assignee_type", "student")
        assignee_ids = data.get("assignee_ids", [])
        duty_title = data.get("duty_title", "").strip()
        duty_category_id = data.get("duty_category") or None
        if duty_category_id:
            try:
                duty_category_id = int(duty_category_id)
            except (ValueError, TypeError):
                duty_category_id = None
        location = data.get("location", "").strip()
        reporting_time = data.get("reporting_time", "").strip()
        instructions = data.get("instructions", "").strip()

        if not taqreeb_id or not duty_title or not assignee_ids:
            return Response(
                {"error": "تقریب، ڈیوٹی عنوان اور افراد کا انتخاب لازمی ہے۔"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check existing duties in this event (one person can only take one duty)
        if assignee_type == "student":
            already_assigned_ids = set(
                DutyAssignment.objects.filter(
                    taqreeb_id=taqreeb_id, student_id__in=assignee_ids
                ).values_list("student_id", flat=True)
            )
        else:
            already_assigned_ids = set(
                DutyAssignment.objects.filter(
                    taqreeb_id=taqreeb_id, staff_id__in=assignee_ids
                ).values_list("staff_id", flat=True)
            )

        available_ids = [aid for aid in assignee_ids if aid not in already_assigned_ids]
        if not available_ids:
            return Response(
                {
                    "error": "منتخب کردہ تمام افراد کو پہلے ہی اس تقریب میں ڈیوٹیاں تفویض کی جا چکی ہیں۔ ایک فرد کو صرف ایک ڈیوٹی دی جا سکتی ہے۔"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_assignments = []
        for a_id in available_ids:
            kwargs = {
                "madrasa": tenant,
                "taqreeb_id": taqreeb_id,
                "duty_category_id": duty_category_id,
                "duty_title": duty_title,
                "assignee_type": assignee_type,
                "location": location,
                "reporting_time": reporting_time,
                "instructions": instructions,
            }
            if assignee_type == "student":
                kwargs["student_id"] = a_id
            else:
                kwargs["staff_id"] = a_id

            duty = DutyAssignment.objects.create(**kwargs)
            created_assignments.append(duty.id)

        skipped_count = len(assignee_ids) - len(created_assignments)
        msg = f"{len(created_assignments)} افراد کو ڈیوٹی کامیابی سے تفویض کر دی گئی۔"
        if skipped_count > 0:
            msg += f" ({skipped_count} افراد کو چھوڑ دیا گیا کیونکہ انہیں پہلے ہی ڈیوٹی لگی ہوئی ہے)"

        return Response(
            {
                "status": "ok",
                "message": msg,
                "assigned_ids": created_assignments,
                "skipped_count": skipped_count,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Taqreeb"])
class GuestInvitationViewSet(TaqreebBaseViewSet):
    queryset = GuestInvitation.objects.select_related("taqreeb")
    serializer_class = GuestInvitationSerializer
    search_fields = [
        "guest_name",
        "designation",
        "organization",
        "phone",
        "city",
        "invitation_number",
    ]
    ordering_fields = ["id", "created_at", "status", "guest_name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        taqreeb_id = self.request.query_params.get("taqreeb")
        status_filter = self.request.query_params.get("status")
        is_special = self.request.query_params.get("is_special_guest")

        if taqreeb_id:
            queryset = queryset.filter(taqreeb_id=taqreeb_id)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if is_special in ["true", "1"]:
            queryset = queryset.filter(is_special_guest=True)

        return queryset

