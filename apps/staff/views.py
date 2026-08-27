from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets

from .models import HalaqaAssignment, Staff, StaffAttendance
from .serializers import HalaqaAssignmentSerializer, StaffAttendanceSerializer, StaffSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Staff"])
class StaffViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Staff.objects.select_related("user")
    serializer_class = StaffSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "phone", "cnic", "role"]
    ordering_fields = ["full_name", "hire_date", "role"]

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get("role")
        return queryset.filter(role=role) if role else queryset


@extend_schema(tags=["Staff"])
class StaffAttendanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = StaffAttendance.objects.select_related("staff")
    serializer_class = StaffAttendanceSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "status"]


@extend_schema(tags=["Staff"])
class HalaqaAssignmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HalaqaAssignment.objects.select_related("staff", "halaqa")
    serializer_class = HalaqaAssignmentSerializer
