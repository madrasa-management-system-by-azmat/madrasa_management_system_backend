from django.db.models import Q
from django.utils import timezone

from .models import PermissionDefinition, RolePermission, TenantRole, UserRoleAssignment

PERMISSION_CATALOG = {
    "dashboard.view": ("dashboard", "view", "ڈیش بورڈ دیکھیں", False),
    "students.view": ("students", "view", "طلبہ دیکھیں", False),
    "students.manage": ("students", "manage", "طلبہ کا انتظام", False),
    "academics.view": ("academics", "view", "تعلیمی امور دیکھیں", False),
    "academics.manage": ("academics", "manage", "تعلیمی امور کا انتظام", False),
    "staff.view": ("staff", "view", "اساتذہ و عملہ دیکھیں", False),
    "staff.manage": ("staff", "manage", "اساتذہ و عملہ کا انتظام", False),
    "hifz.view": ("hifz", "view", "حفظ ریکارڈ دیکھیں", False),
    "hifz.manage": ("hifz", "manage", "حفظ ریکارڈ کا انتظام", False),
    "hostel.view": ("hostel", "view", "ہاسٹل دیکھیں", False),
    "hostel.manage": ("hostel", "manage", "ہاسٹل کا انتظام", False),
    "attendance.view": ("attendance", "view", "حاضری دیکھیں", False),
    "attendance.manage": ("attendance", "manage", "حاضری درج و تبدیل کریں", False),
    "exams.view": ("exams", "view", "امتحانات دیکھیں", False),
    "exams.manage": ("exams", "manage", "امتحانات کا انتظام", False),
    "exams.finalize": ("exams", "finalize", "نتائج حتمی و شائع کریں", True),
    "finance.view": ("finance", "view", "مالیات دیکھیں", True),
    "finance.manage": ("finance", "manage", "مالی ریکارڈ کا انتظام", True),
    "finance.approve": ("finance", "approve", "بجٹ و پے رول منظور کریں", True),
    "finance.payroll.pay": ("finance", "payroll_pay", "پے رول ادا کریں", True),
    "library.view": ("library", "view", "لائبریری دیکھیں", False),
    "library.manage": ("library", "manage", "لائبریری کا انتظام", False),
    "fatwas.view": ("fatwas", "view", "فتاویٰ دیکھیں", True),
    "fatwas.manage": ("fatwas", "manage", "فتاویٰ کا انتظام", True),
    "meetings.view": ("meetings", "view", "اجلاس دیکھیں", False),
    "meetings.manage": ("meetings", "manage", "اجلاس کا انتظام", False),
    "tasks.view": ("tasks", "view", "انتظامی کام دیکھیں", False),
    "tasks.manage": ("tasks", "manage", "انتظامی کام کا انتظام", False),
    "documents.view": ("documents", "view", "دستاویزات دیکھیں", True),
    "documents.manage": ("documents", "manage", "دستاویزات کا انتظام", True),
    "guardians.view": ("guardians", "view", "سرپرست ریکارڈ دیکھیں", True),
    "guardians.manage": ("guardians", "manage", "سرپرست ریکارڈ کا انتظام", True),
    "leaves.view": ("leaves", "view", "رخصتیں دیکھیں", False),
    "leaves.manage": ("leaves", "manage", "رخصتوں کا انتظام", False),
    "development.view": ("development", "view", "طلبہ ترقی دیکھیں", True),
    "development.manage": ("development", "manage", "طلبہ ترقی کا انتظام", True),
    "certificates.view": ("certificates", "view", "اسناد دیکھیں", False),
    "certificates.manage": ("certificates", "manage", "اسناد جاری و منسوخ کریں", True),
    "operations.view": ("operations", "view", "عملی انتظام دیکھیں", False),
    "operations.manage": ("operations", "manage", "عملی ریکارڈ کا انتظام", True),
    "users.view": ("users", "view", "صارفین دیکھیں", True),
    "users.manage": ("users", "manage", "صارفین کا انتظام", True),
    "roles.view": ("roles", "view", "کردار اور اجازتیں دیکھیں", True),
    "roles.manage": ("roles", "manage", "کردار اور اجازتیں منظم کریں", True),
    "settings.view": ("settings", "view", "ترتیبات دیکھیں", True),
    "settings.manage": ("settings", "manage", "ترتیبات تبدیل کریں", True),
    "settings.backup": ("settings", "backup", "بیک اپ بنائیں", True),
    "settings.restore": ("settings", "restore", "بیک اپ بحال کریں", True),
    "audit.view": ("audit", "view", "آڈٹ لاگز دیکھیں", True),
    "audit.manage": ("audit", "manage", "آرکائیو اور قانونی پابندیاں منظم کریں", True),
    "parent.portal.view": ("parent", "view", "والدین پورٹل دیکھیں", True),
}

MODULE_APP_MAP = {
    "students": "students", "academics": "academics", "staff": "staff",
    "hifz": "hifz", "hostel": "hostel", "exams": "exams",
    "finance": "finance", "library": "library", "fatwas": "fatwas",
    "meetings": "meetings", "tasks": "tasks", "documents": "documents",
    "guardians": "guardians", "leaves": "leaves", "development": "development",
    "certificates": "certificates", "operations": "operations", "auditlog": "audit",
}

SYSTEM_ROLES = {
    "admin": {"name": "Administrator", "name_ur": "منتظم", "permissions": "*"},
    "operator": {"name": "Operator", "name_ur": "آپریٹر", "permissions": "operator"},
    "accountant": {"name": "Accountant", "name_ur": "اکاؤنٹنٹ", "permissions": "accountant"},
    "guardian": {"name": "Guardian", "name_ur": "سرپرست", "permissions": "guardian"},
}


def permission_codes_for_legacy_role(role):
    codes = set()
    if role == "admin":
        return set(PERMISSION_CATALOG)
    if role == "operator":
        for code, (module, _action, _name, _sensitive) in PERMISSION_CATALOG.items():
            if module not in {"finance", "users", "roles", "settings", "audit", "parent"}:
                codes.add(code)
    elif role == "accountant":
        codes.update({"dashboard.view", "finance.view", "finance.manage", "finance.payroll.pay", "leaves.view"})
    elif role == "guardian":
        codes.add("parent.portal.view")
    return codes


def seed_permission_catalog():
    definitions = {}
    for code, (module, action, name, sensitive) in PERMISSION_CATALOG.items():
        definition, _ = PermissionDefinition.objects.update_or_create(
            code=code,
            defaults={"module": module, "action": action, "name": name, "is_sensitive": sensitive, "is_active": True},
        )
        definitions[code] = definition
    return definitions


def ensure_tenant_system_roles(madrasa, *, assigned_by=None):
    definitions = seed_permission_catalog()
    roles = {}
    for legacy_key, config in SYSTEM_ROLES.items():
        role, _ = TenantRole.objects.update_or_create(
            madrasa=madrasa,
            legacy_key=legacy_key,
            defaults={"slug": legacy_key, "name": config["name"], "name_ur": config["name_ur"], "is_system": True, "is_active": True, "created_by": assigned_by},
        )
        codes = permission_codes_for_legacy_role(legacy_key)
        RolePermission.objects.filter(role=role).exclude(permission__code__in=codes).delete()
        existing = set(RolePermission.objects.filter(role=role).values_list("permission__code", flat=True))
        RolePermission.objects.bulk_create([RolePermission(role=role, permission=definitions[code]) for code in codes - existing])
        roles[legacy_key] = role
    return roles


def sync_legacy_assignment(profile, *, assigned_by=None):
    if not profile.madrasa_id or not profile.role:
        return None
    roles = ensure_tenant_system_roles(profile.madrasa, assigned_by=assigned_by)
    role = roles[profile.role]
    assignment, _ = UserRoleAssignment.objects.update_or_create(
        madrasa=profile.madrasa, user=profile.user, role=role,
        defaults={"is_active": True, "expires_at": None, "revoked_at": None, "revoked_by": None, "assigned_by": assigned_by},
    )
    UserRoleAssignment.objects.filter(madrasa=profile.madrasa, user=profile.user, role__is_system=True).exclude(pk=assignment.pk).update(is_active=False, revoked_at=timezone.now(), revoked_by=assigned_by)
    return assignment


def effective_permissions(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return set()
    profile = getattr(user, "profile", None)
    if not profile or not profile.madrasa_id or not profile.madrasa.is_active:
        return set()
    now = timezone.now()
    assignments = UserRoleAssignment.objects.filter(
        madrasa=profile.madrasa, user=user, is_active=True, starts_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    codes = set(RolePermission.objects.filter(role__user_assignments__in=assignments, role__is_active=True, permission__is_active=True).values_list("permission__code", flat=True))
    if not assignments.exists():
        sync_legacy_assignment(profile)
        return permission_codes_for_legacy_role(profile.role)
    return codes


def user_has_permission(user, code):
    return code in effective_permissions(user)


def permission_for_view(request, view):
    explicit = getattr(view, "required_permission", None)
    action = getattr(view, "action", None)
    action_permissions = getattr(view, "action_permissions", {})
    if action in action_permissions:
        return action_permissions[action]
    if explicit:
        return explicit
    app_label = view.__class__.__module__.split(".")[1] if "." in view.__class__.__module__ else ""
    module = MODULE_APP_MAP.get(app_label)
    if not module:
        return None
    mode = "view" if request.method in ("GET", "HEAD", "OPTIONS") else "manage"
    return f"{module}.{mode}"
