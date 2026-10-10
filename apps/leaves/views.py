from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.users.tenancy import TenantScopedViewSetMixin
from .models import InstitutionCalendarDay, LeaveAttachment, LeaveAuditEvent, LeaveBalance, LeavePolicy, LeavePolicyRule, LeaveRequest, LeaveSubstitution, LeaveType
from .serializers import InstitutionCalendarDaySerializer, LeaveAttachmentSerializer, LeaveBalanceSerializer, LeavePolicyRuleSerializer, LeavePolicySerializer, LeaveRequestSerializer, LeaveSubstitutionSerializer, LeaveTypeSerializer


class LeaveAccess(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "profile", None)
        return bool(profile and profile.madrasa_id and profile.role in ["admin", "operator", "accountant", "guardian"])


class LeaveBaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [LeaveAccess]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Leave Management"])
class InstitutionCalendarDayViewSet(LeaveBaseViewSet):
    queryset = InstitutionCalendarDay.objects.select_related("academic_class", "created_by")
    serializer_class = InstitutionCalendarDaySerializer
    ordering_fields = ["date", "audience", "day_type"]

    def perform_create(self, serializer):
        if self.request.user.profile.role == "guardian":
            raise PermissionDenied("Staff access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Leave Management"])
class LeaveTypeViewSet(LeaveBaseViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["subject_kind", "name"]

    def perform_create(self, serializer):
        if self.request.user.profile.role != "admin":
            raise PermissionDenied("Only administrators can configure leave types.")
        super().perform_create(serializer)


@extend_schema(tags=["Leave Management"])
class LeavePolicyViewSet(LeaveBaseViewSet):
    queryset = LeavePolicy.objects.prefetch_related("rules__leave_type")
    serializer_class = LeavePolicySerializer

    def perform_create(self, serializer):
        if self.request.user.profile.role != "admin":
            raise PermissionDenied("Only administrators can configure leave policies.")
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)


@extend_schema(tags=["Leave Management"])
class LeavePolicyRuleViewSet(LeaveBaseViewSet):
    queryset = LeavePolicyRule.objects.select_related("policy", "leave_type")
    serializer_class = LeavePolicyRuleSerializer


@extend_schema(tags=["Leave Management"])
class LeaveBalanceViewSet(LeaveBaseViewSet):
    queryset = LeaveBalance.objects.select_related("staff", "student", "leave_type")
    serializer_class = LeaveBalanceSerializer
    search_fields = ["staff__full_name", "student__full_name", "leave_type__name"]
    ordering_fields = ["year", "leave_type__name"]


@extend_schema(tags=["Leave Management"])
class LeaveRequestViewSet(LeaveBaseViewSet):
    queryset = LeaveRequest.objects.select_related("staff", "student", "guardian", "leave_type", "approved_by", "rejected_by").prefetch_related("days", "substitutions__substitute_staff", "attachments", "audit_events__actor")
    serializer_class = LeaveRequestSerializer
    search_fields = ["request_number", "staff__full_name", "student__full_name", "reason", "leave_type__name"]
    ordering_fields = ["starts_on", "ends_on", "status", "created_at", "chargeable_days"]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.user.profile.role
        if role == "guardian":
            guardian = self.request.user.guardian_profile
            queryset = queryset.filter(guardian=guardian, student__guardian_links__guardian=guardian, student__guardian_links__portal_access_enabled=True, student__guardian_links__revoked_at__isnull=True).distinct()
        elif role == "accountant":
            queryset = queryset.filter(subject_kind=LeaveRequest.SubjectKind.STAFF, status=LeaveRequest.Status.APPROVED)
        for field in ["status", "subject_kind", "leave_type", "staff", "student"]:
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    def perform_create(self, serializer):
        role = self.request.user.profile.role
        extra = {"madrasa": self.get_madrasa()}
        if role == "guardian":
            guardian = self.request.user.guardian_profile
            student = serializer.validated_data.get("student")
            if serializer.validated_data.get("subject_kind") != LeaveRequest.SubjectKind.STUDENT or not guardian.student_links.filter(student=student, portal_access_enabled=True, revoked_at__isnull=True, is_legal_guardian=True).exists():
                raise PermissionDenied("Guardians can request leave only for linked students.")
            extra["guardian"] = guardian
        elif role == "accountant":
            raise PermissionDenied("Accountants cannot submit leave requests.")
        serializer.save(**extra)

    def perform_update(self, serializer):
        request = serializer.instance
        if request.status != LeaveRequest.Status.DRAFT:
            raise serializers.ValidationError("Only draft leave requests can be edited.")
        if self.request.user.profile.role == "guardian" and request.guardian_id != self.request.user.guardian_profile.id:
            raise PermissionDenied("This request does not belong to the guardian.")
        serializer.save()

    def _event(self, request_obj, action_name, old_status, comment=""):
        LeaveAuditEvent.objects.create(madrasa=self.get_madrasa(), request=request_obj, action=action_name, from_status=old_status, to_status=request_obj.status, actor=self.request.user, comment=comment)

    def _transition(self, request_obj, allowed, target, action_name, comment="", fields=None):
        if request_obj.status not in allowed:
            return Response({"detail": "This workflow action is not allowed in the current state."}, status=status.HTTP_400_BAD_REQUEST)
        old = request_obj.status
        request_obj.status = target
        update_fields = ["status", "updated_at"]
        for key, value in (fields or {}).items():
            setattr(request_obj, key, value)
            update_fields.append(key)
        request_obj.save(update_fields=update_fields)
        self._event(request_obj, action_name, old, comment)
        return Response(self.get_serializer(request_obj).data)

    @action(detail=False, methods=["get"])
    def people_lookup(self, request):
        if request.user.profile.role == "guardian":
            guardian = request.user.guardian_profile
            students = guardian.student_links.filter(portal_access_enabled=True, revoked_at__isnull=True).values("student_id", "student__full_name", "student__registration_number")
            return Response({"staff": [], "students": list(students)})
        from apps.staff.models import Staff
        from apps.students.models import Student
        return Response({"staff": list(Staff.objects.filter(madrasa=self.get_madrasa(), is_active=True).values("id", "full_name", "role")), "students": list(Student.objects.filter(madrasa=self.get_madrasa(), status__in=["active", "on_leave"]).values("id", "full_name", "registration_number"))})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        leave = self.get_object()
        if leave.leave_type.requires_attachment and leave.chargeable_days >= leave.leave_type.attachment_required_after_days and not leave.attachments.exists():
            return Response({"detail": "A supporting attachment is required."}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(leave, [LeaveRequest.Status.DRAFT], LeaveRequest.Status.PENDING_APPROVAL, "submitted", request.data.get("comment", ""), {"submitted_at": timezone.now()})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can approve leave."}, status=status.HTTP_403_FORBIDDEN)
        leave = self.get_object()
        if leave.status != LeaveRequest.Status.PENDING_APPROVAL:
            return Response({"detail": "Submit the request before approval."}, status=status.HTTP_400_BAD_REQUEST)
        balance = LeaveBalance.objects.filter(madrasa=self.get_madrasa(), leave_type=leave.leave_type, year=leave.starts_on.year, staff=leave.staff if leave.staff_id else None, student=leave.student if leave.student_id else None).first()
        if balance and not leave.leave_type.allow_negative_balance and balance.available < leave.chargeable_days:
            return Response({"detail": "Insufficient leave balance."}, status=status.HTTP_400_BAD_REQUEST)
        if balance:
            balance.used += leave.chargeable_days
            balance.save(update_fields=["used"])
        return self._transition(leave, [LeaveRequest.Status.PENDING_APPROVAL], LeaveRequest.Status.APPROVED, "approved", request.data.get("comment", ""), {"approved_by": request.user, "approved_at": timezone.now(), "decision_notes": request.data.get("comment", "")})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if request.user.profile.role != "admin":
            return Response({"detail": "Only administrators can reject leave."}, status=status.HTTP_403_FORBIDDEN)
        comment = str(request.data.get("comment", "")).strip()
        if not comment:
            return Response({"comment": ["A rejection reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        return self._transition(self.get_object(), [LeaveRequest.Status.PENDING_APPROVAL], LeaveRequest.Status.REJECTED, "rejected", comment, {"rejected_by": request.user, "rejected_at": timezone.now(), "decision_notes": comment})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def cancel(self, request, pk=None):
        leave = self.get_object()
        reason = str(request.data.get("reason", "")).strip()
        if not reason:
            return Response({"reason": ["Cancellation reason is required."]}, status=status.HTTP_400_BAD_REQUEST)
        if leave.status == LeaveRequest.Status.APPROVED:
            balance = LeaveBalance.objects.filter(madrasa=self.get_madrasa(), leave_type=leave.leave_type, year=leave.starts_on.year, staff=leave.staff if leave.staff_id else None, student=leave.student if leave.student_id else None).first()
            if balance:
                balance.used = max(balance.used - leave.chargeable_days, Decimal("0"))
                balance.save(update_fields=["used"])
        return self._transition(leave, [LeaveRequest.Status.DRAFT, LeaveRequest.Status.PENDING_APPROVAL, LeaveRequest.Status.APPROVED], LeaveRequest.Status.CANCELLED, "cancelled", reason, {"cancellation_reason": reason, "cancelled_by": request.user, "cancelled_at": timezone.now()})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def sync_attendance(self, request, pk=None):
        leave = self.get_object()
        if leave.status != LeaveRequest.Status.APPROVED:
            return Response({"detail": "Only approved leave can be synchronized."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.profile.role == "guardian":
            return Response({"detail": "Staff access is required."}, status=status.HTTP_403_FORBIDDEN)
        count = 0
        if leave.student_id:
            from apps.students.models import StudentAttendance
            for day in leave.days.filter(is_chargeable=True):
                _, created = StudentAttendance.objects.get_or_create(madrasa=self.get_madrasa(), student=leave.student, date=day.date, defaults={"status": leave.leave_type.attendance_status, "recorded_by": request.user})
                count += int(created)
        else:
            from apps.staff.models import StaffAttendance
            for day in leave.days.filter(is_chargeable=True):
                _, created = StaffAttendance.objects.get_or_create(madrasa=self.get_madrasa(), staff=leave.staff, date=day.date, defaults={"status": "leave", "recorded_by": request.user, "remarks": leave.request_number})
                count += int(created)
        self._event(leave, "attendance_synchronized", leave.status, f"{count} attendance rows created")
        return Response({"created": count})


@extend_schema(tags=["Leave Management"])
class LeaveSubstitutionViewSet(LeaveBaseViewSet):
    queryset = LeaveSubstitution.objects.select_related("request", "teaching_assignment__academic_class", "teaching_assignment__subject", "substitute_staff")
    serializer_class = LeaveSubstitutionSerializer

    def perform_create(self, serializer):
        if self.request.user.profile.role == "guardian":
            raise PermissionDenied("Staff access is required.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), assigned_by=self.request.user)


@extend_schema(tags=["Leave Management"])
class LeaveAttachmentViewSet(LeaveBaseViewSet):
    queryset = LeaveAttachment.objects.select_related("request", "uploaded_by")
    serializer_class = LeaveAttachmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.profile.role == "guardian":
            queryset = queryset.filter(request__guardian=self.request.user.guardian_profile)
        return queryset

    def perform_create(self, serializer):
        leave = serializer.validated_data["request"]
        if self.request.user.profile.role == "guardian" and leave.guardian_id != self.request.user.guardian_profile.id:
            raise PermissionDenied("This request does not belong to the guardian.")
        upload = serializer.validated_data["file"]
        serializer.save(madrasa=self.get_madrasa(), original_name=upload.name, uploaded_by=self.request.user)


class LeaveDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    permission_classes = [LeaveAccess]
    queryset = LeaveRequest.objects.none()

    def list(self, request):
        queryset = LeaveRequest.objects.filter(madrasa=self.get_madrasa())
        if request.user.profile.role == "guardian":
            queryset = queryset.filter(guardian=request.user.guardian_profile)
        today = timezone.localdate()
        return Response({"total": queryset.count(), "pending": queryset.filter(status=LeaveRequest.Status.PENDING_APPROVAL).count(), "approved": queryset.filter(status=LeaveRequest.Status.APPROVED).count(), "active_today": queryset.filter(status=LeaveRequest.Status.APPROVED, starts_on__lte=today, ends_on__gte=today).count(), "staff_active": queryset.filter(subject_kind=LeaveRequest.SubjectKind.STAFF, status=LeaveRequest.Status.APPROVED, starts_on__lte=today, ends_on__gte=today).count(), "student_active": queryset.filter(subject_kind=LeaveRequest.SubjectKind.STUDENT, status=LeaveRequest.Status.APPROVED, starts_on__lte=today, ends_on__gte=today).count(), "days_approved": queryset.filter(status=LeaveRequest.Status.APPROVED).aggregate(value=Sum("chargeable_days"))["value"] or Decimal("0"), "recent": LeaveRequestSerializer(queryset[:10], many=True, context={"request": request}).data})
