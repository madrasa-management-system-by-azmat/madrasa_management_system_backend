from rest_framework.exceptions import PermissionDenied, ValidationError

from .permissions import HasTenantRole


def current_madrasa(request):
    profile = getattr(request.user, "profile", None)
    if not profile or not profile.madrasa_id or not profile.madrasa.is_active:
        raise PermissionDenied("An active madrasa membership is required.")
    return profile.madrasa


class TenantScopedViewSetMixin:
    """Filters standard API records by the current user's madrasa."""

    tenant_lookup = "madrasa"
    permission_classes = [HasTenantRole]

    def get_madrasa(self):
        return current_madrasa(self.request)

    def get_queryset(self):
        return super().get_queryset().filter(**{self.tenant_lookup: self.get_madrasa()})

    def perform_create(self, serializer):
        tenant = self.get_madrasa()
        self._validate_tenant_relations(serializer.validated_data, tenant)
        serializer.save(madrasa=tenant)

    def perform_update(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save()

    def _validate_tenant_relations(self, value, tenant):
        """Reject writable relations that point outside the active madrasa."""
        if isinstance(value, dict):
            for item in value.values():
                self._validate_tenant_relations(item, tenant)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._validate_tenant_relations(item, tenant)
            return
        if hasattr(value, "madrasa_id") and value.madrasa_id and value.madrasa_id != tenant.id:
            raise ValidationError("Related records must belong to the active madrasa.")