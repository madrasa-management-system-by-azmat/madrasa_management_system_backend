from drf_spectacular.utils import extend_schema
from rest_framework import filters, viewsets

from .models import HifzDailyLog
from .serializers import HifzDailyLogSerializer
from apps.users.tenancy import TenantScopedViewSetMixin


@extend_schema(tags=["Hifz"])
class HifzDailyLogViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = HifzDailyLog.objects.select_related("student", "verified_by")
    serializer_class = HifzDailyLogSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__full_name", "student__registration_number"]
    ordering_fields = ["date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        date = self.request.query_params.get("date")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        student = self.request.query_params.get("student")

        if date:
            queryset = queryset.filter(date=date)
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        if student:
            queryset = queryset.filter(student_id=student)

        return queryset
