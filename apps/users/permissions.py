from rest_framework.permissions import BasePermission


class HasTenantRole(BasePermission):
    """Central role policy. Super admins are Django platform superusers."""

    finance_paths = {"finance", "fund", "donor", "donation", "student-fee", "student-monthly-fee", "student-fee-payment", "teacher-salary", "student-sponsorship", "expense"}

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return False
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.madrasa_id or not profile.madrasa.is_active:
            return False
        if profile.role == "admin":
            return True
        basename = getattr(view, "basename", "")
        is_finance_view = basename in self.finance_paths or view.__class__.__module__.startswith("apps.finance")
        action = getattr(view, "action", None)
        is_write = request.method not in ("GET", "HEAD", "OPTIONS")
        if profile.role == "operator":
            return not is_finance_view and basename != "madrasa-users"
        if profile.role == "accountant":
            return is_finance_view
        return not is_write