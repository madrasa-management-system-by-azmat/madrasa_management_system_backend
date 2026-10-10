from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.tenancy import TenantScopedViewSetMixin
from .models import GuardianAnnouncement, GuardianAnnouncementRead, GuardianConsent, GuardianInvitation, GuardianNotificationPreference, GuardianProfile, GuardianStudentLink, ParentMeetingBooking, ParentMeetingSlot
from .serializers import CreateGuardianSerializer, GuardianAnnouncementSerializer, GuardianProfileSerializer, ParentMeetingBookingSerializer, ParentMeetingSlotSerializer

User = get_user_model()


class IsGuardian(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "guardian_profile") and request.user.guardian_profile.status == GuardianProfile.Status.ACTIVE)


class IsPortalOrTenantStaff(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "profile", None)
        return bool(profile and profile.madrasa_id and (profile.role in ["admin", "operator"] or hasattr(request.user, "guardian_profile")))


class GuardianActivationAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        invitation = GuardianInvitation.objects.filter(token_hash=GuardianInvitation.token_digest(token), used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).select_related("guardian__madrasa").first()
        if not invitation:
            return Response({"detail": "Invitation is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        guardian = invitation.guardian
        return Response({"madrasa": guardian.madrasa.name, "guardian": guardian.full_name, "phone": f"******{guardian.normalized_phone[-4:]}"})

    @transaction.atomic
    def post(self, request, token):
        invitation = GuardianInvitation.objects.select_for_update().filter(token_hash=GuardianInvitation.token_digest(token), used_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).select_related("guardian__user").first()
        if not invitation:
            return Response({"detail": "Invitation is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        password = request.data.get("password", "")
        if len(password) < 8:
            return Response({"password": ["Password must contain at least 8 characters."]}, status=status.HTTP_400_BAD_REQUEST)
        guardian = invitation.guardian
        guardian.user.set_password(password)
        guardian.user.is_active = True
        guardian.user.save(update_fields=["password", "is_active"])
        guardian.status = GuardianProfile.Status.ACTIVE
        guardian.phone_verified_at = timezone.now()
        guardian.save(update_fields=["status", "phone_verified_at", "updated_at"])
        invitation.used_at = timezone.now()
        invitation.save(update_fields=["used_at"])
        GuardianConsent.objects.create(madrasa=guardian.madrasa, guardian=guardian, terms_version="1.0", privacy_version="1.0", communication_consent=bool(request.data.get("communication_consent", True)))
        GuardianNotificationPreference.objects.get_or_create(madrasa=guardian.madrasa, guardian=guardian)
        refresh = RefreshToken.for_user(guardian.user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "user": {"id": guardian.user_id, "username": guardian.user.username, "role": "guardian", "madrasa_id": guardian.madrasa_id, "madrasa_name": guardian.madrasa.name}})


@extend_schema(tags=["Parent Portal Management"])
class GuardianManagementViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = GuardianProfile.objects.select_related("user").prefetch_related("student_links__student__current_class")
    serializer_class = GuardianProfileSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "phone", "email", "student_links__student__full_name", "student_links__student__registration_number"]
    ordering_fields = ["full_name", "status", "created_at"]

    def _admin(self):
        if self.request.user.profile.role != "admin":
            raise PermissionDenied("Only administrators can manage guardians.")

    def list(self, request, *args, **kwargs):
        self._admin()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._admin()
        return super().retrieve(request, *args, **kwargs)

    @action(detail=False, methods=["post"])
    def create_guardian(self, request):
        self._admin()
        serializer = CreateGuardianSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        guardian = serializer.save()
        return Response(self.get_serializer(guardian).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        self._admin()
        guardian = self.get_object()
        guardian.invitations.filter(used_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
        invitation, token = GuardianInvitation.issue(guardian, request.user)
        return Response({"detail": "Invitation created.", "token": token, "expires_at": invitation.expires_at})

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        self._admin()
        guardian = self.get_object()
        guardian.status = GuardianProfile.Status.SUSPENDED
        guardian.user.is_active = False
        guardian.user.save(update_fields=["is_active"])
        guardian.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(guardian).data)


class ParentPortalAPIView(APIView):
    permission_classes = [IsAuthenticated, IsGuardian]

    def _guardian(self, request):
        return request.user.guardian_profile

    def _student(self, guardian, student_id):
        link = GuardianStudentLink.objects.filter(guardian=guardian, student_id=student_id, portal_access_enabled=True, revoked_at__isnull=True).select_related("student__current_class", "student__current_halaqa").first()
        if not link:
            raise PermissionDenied("This student is not linked to the guardian account.")
        return link.student

    def get(self, request):
        from apps.exams.models import InternalExamResult
        from apps.finance.models import StudentMonthlyFee
        from apps.hifz.models import HifzDailyLog
        from apps.students.models import StudentAttendance
        guardian = self._guardian(request)
        links = guardian.student_links.filter(portal_access_enabled=True, revoked_at__isnull=True).select_related("student__current_class", "student__current_halaqa")
        children = []
        for link in links:
            student = link.student
            attendance = StudentAttendance.objects.filter(madrasa=guardian.madrasa, student=student)
            fees = StudentMonthlyFee.objects.filter(madrasa=guardian.madrasa, student=student).prefetch_related("payments")
            results = InternalExamResult.objects.filter(madrasa=guardian.madrasa, student=student, exam__status="published").select_related("exam", "subject").order_by("-exam__exam_date")[:10]
            hifz = HifzDailyLog.objects.filter(madrasa=guardian.madrasa, student=student).order_by("-date")[:7]
            children.append({"id": student.id, "registration_number": student.registration_number, "full_name": student.full_name, "photo": student.photo.url if student.photo else None, "class_name": student.current_class.name if student.current_class_id else "", "halaqa_name": student.current_halaqa.name if student.current_halaqa_id else "", "attendance": {"total": attendance.count(), "present": attendance.filter(status="present").count(), "absent": attendance.filter(status="absent").count(), "late": attendance.filter(status="late").count(), "recent": list(attendance.order_by("-date").values("date", "status")[:10])}, "fees": {"outstanding": sum((fee.outstanding_balance for fee in fees), 0), "recent": [{"month": fee.month, "total_due": fee.total_due, "amount_paid": fee.amount_paid, "outstanding": fee.outstanding_balance} for fee in fees[:6]]}, "results": [{"exam": row.exam.name, "date": row.exam.exam_date, "subject": row.subject.name if row.subject else "", "marks": row.marks, "result": row.result} for row in results], "hifz": [{"date": row.date, "sabaq": row.sabaq_portion, "sabqi": row.sabaqi_portion, "manzil": row.manzil_portion} for row in hifz]})
        student_ids = [link.student_id for link in links]
        class_ids = [link.student.current_class_id for link in links if link.student.current_class_id]
        announcements = GuardianAnnouncement.objects.filter(madrasa=guardian.madrasa, published_at__lte=timezone.now()).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).filter(Q(audience="all") | Q(audience="class", academic_class_id__in=class_ids) | Q(audience="individual", student_id__in=student_ids)).distinct()[:20]
        bookings = ParentMeetingBooking.objects.filter(madrasa=guardian.madrasa, guardian=guardian).select_related("slot__teacher", "student")[:10]
        slots = ParentMeetingSlot.objects.filter(madrasa=guardian.madrasa, status=ParentMeetingSlot.Status.OPEN, starts_at__gt=timezone.now()).filter(Q(academic_class__isnull=True) | Q(academic_class_id__in=class_ids)).select_related("teacher", "academic_class").prefetch_related("bookings")[:30]
        return Response({"guardian": GuardianProfileSerializer(guardian).data, "children": children, "announcements": GuardianAnnouncementSerializer(announcements, many=True, context={"guardian": guardian}).data, "meetings": ParentMeetingBookingSerializer(bookings, many=True).data, "available_slots": ParentMeetingSlotSerializer(slots, many=True).data})


@extend_schema(tags=["Parent Meetings"])
class ParentMeetingSlotViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ParentMeetingSlot.objects.select_related("teacher", "academic_class", "created_by").prefetch_related("bookings")
    serializer_class = ParentMeetingSlotSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["teacher__full_name", "academic_class__name", "venue"]
    ordering_fields = ["starts_at", "status"]
    permission_classes = [IsPortalOrTenantStaff]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "guardian":
            guardian = self.request.user.guardian_profile
            class_ids = guardian.student_links.filter(portal_access_enabled=True, revoked_at__isnull=True).values_list("student__current_class_id", flat=True)
            queryset = queryset.filter(status=ParentMeetingSlot.Status.OPEN, starts_at__gt=timezone.now()).filter(Q(academic_class__isnull=True) | Q(academic_class_id__in=class_ids))
        return queryset

    def perform_create(self, serializer):
        if self.request.user.profile.role == "guardian":
            raise PermissionDenied("Staff access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Parent Meetings"])
class ParentMeetingBookingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = ParentMeetingBooking.objects.select_related("slot__teacher", "guardian", "student")
    serializer_class = ParentMeetingBookingSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["guardian__full_name", "student__full_name", "slot__teacher__full_name"]
    ordering_fields = ["slot__starts_at", "status"]
    permission_classes = [IsPortalOrTenantStaff]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "guardian":
            queryset = queryset.filter(guardian=self.request.user.guardian_profile)
        return queryset

    def perform_create(self, serializer):
        if self.request.user.profile.role != "guardian":
            raise PermissionDenied("Guardians book appointments through the parent portal.")
        guardian = self.request.user.guardian_profile
        slot = serializer.validated_data["slot"]
        student = serializer.validated_data["student"]
        if not GuardianStudentLink.objects.filter(guardian=guardian, student=student, portal_access_enabled=True, revoked_at__isnull=True).exists():
            raise PermissionDenied("This student is not linked to the guardian account.")
        if slot.status != ParentMeetingSlot.Status.OPEN or slot.starts_at <= timezone.now() or slot.bookings.exclude(status=ParentMeetingBooking.Status.CANCELLED).count() >= slot.capacity:
            raise serializers.ValidationError("This appointment slot is not available.")
        serializer.save(madrasa=self.get_madrasa(), guardian=guardian)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        booking = self.get_object()
        if request.user.profile.role == "guardian":
            return Response({"detail": "Staff access is required."}, status=status.HTTP_403_FORBIDDEN)
        booking.status = ParentMeetingBooking.Status.COMPLETED
        booking.teacher_notes = request.data.get("teacher_notes", booking.teacher_notes)
        booking.follow_up = request.data.get("follow_up", booking.follow_up)
        booking.follow_up_due = request.data.get("follow_up_due") or booking.follow_up_due
        booking.completed_at = timezone.now()
        booking.save(update_fields=["status", "teacher_notes", "follow_up", "follow_up_due", "completed_at"])
        return Response(self.get_serializer(booking).data)


@extend_schema(tags=["Parent Portal Management"])
class GuardianAnnouncementViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = GuardianAnnouncement.objects.select_related("academic_class", "student", "created_by")
    serializer_class = GuardianAnnouncementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body", "academic_class__name", "student__full_name"]
    ordering_fields = ["published_at", "expires_at"]
    permission_classes = [IsPortalOrTenantStaff]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "guardian":
            guardian = self.request.user.guardian_profile
            links = guardian.student_links.filter(portal_access_enabled=True, revoked_at__isnull=True).select_related("student")
            student_ids = [link.student_id for link in links]
            class_ids = [link.student.current_class_id for link in links if link.student.current_class_id]
            queryset = queryset.filter(published_at__lte=timezone.now()).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).filter(Q(audience="all") | Q(audience="class", academic_class_id__in=class_ids) | Q(audience="individual", student_id__in=student_ids)).distinct()
        return queryset

    def perform_create(self, serializer):
        if self.request.user.profile.role == "guardian":
            raise PermissionDenied("Staff access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        if request.user.profile.role != "guardian":
            return Response({"detail": "Guardian access is required."}, status=status.HTTP_403_FORBIDDEN)
        guardian = request.user.guardian_profile
        read, _ = GuardianAnnouncementRead.objects.get_or_create(madrasa=self.get_madrasa(), announcement=self.get_object(), guardian=guardian)
        return Response({"read_at": read.read_at})
