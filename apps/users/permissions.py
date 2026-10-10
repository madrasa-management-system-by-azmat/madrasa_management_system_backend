from rest_framework.permissions import BasePermission

from .rbac import permission_for_view, user_has_permission


class HasTenantRole(BasePermission):
    """Compatibility name for the central permission-based tenant policy."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return False
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.madrasa_id or not profile.madrasa.is_active:
            return False
        required = permission_for_view(request, view)
        return bool(required and user_has_permission(request.user, required))


class HasPermissionCode(BasePermission):
    """Checks ``required_permission`` or per-action ``action_permissions``."""

    def has_permission(self, request, view):
        required = permission_for_view(request, view)
        return bool(required and user_has_permission(request.user, required))