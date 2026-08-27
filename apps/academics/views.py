from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets

from .models import Subject
from .serializers import SubjectSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Academics"])
class SubjectViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Subject.objects.select_related("academic_class")
    serializer_class = SubjectSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "academic_class__name"]
    ordering_fields = ["name", "academic_class__name"]
