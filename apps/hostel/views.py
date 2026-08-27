from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets

from .models import GatePass, HostelAllocation, HostelRoom, HostelWing
from .serializers import GatePassSerializer, HostelAllocationSerializer, HostelRoomSerializer, HostelWingSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Hostel"])
class HostelWingViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HostelWing.objects.all()
    serializer_class = HostelWingSerializer


@extend_schema(tags=["Hostel"])
class HostelRoomViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HostelRoom.objects.select_related("wing")
    serializer_class = HostelRoomSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["room_number", "capacity"]


@extend_schema(tags=["Hostel"])
class HostelAllocationViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HostelAllocation.objects.select_related("student", "room__wing")
    serializer_class = HostelAllocationSerializer


@extend_schema(tags=["Hostel"])
class GatePassViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = GatePass.objects.select_related("student", "authorized_by")
    serializer_class = GatePassSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["out_date", "in_date"]
