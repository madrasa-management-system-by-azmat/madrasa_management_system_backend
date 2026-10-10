from django.conf import settings
from django.db import models
from django.utils import timezone


class Madrasa(models.Model):
    """A tenant boundary for one madrasa and all of its operational data."""

    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        OPERATOR = "operator", "Operator"
        ACCOUNTANT = "accountant", "Accountant"
        GUARDIAN = "guardian", "Guardian"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    madrasa = models.ForeignKey(Madrasa, on_delete=models.PROTECT, related_name="members", null=True, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.OPERATOR)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to="users/photos/", blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class PermissionDefinition(models.Model):
    """Stable application capability shared by every tenant."""

    code = models.CharField(max_length=100, unique=True)
    module = models.CharField(max_length=50, db_index=True)
    action = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    is_sensitive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["module", "code"]

    def __str__(self):
        return self.code


class TenantRole(models.Model):
    """Tenant-defined role composed from named permission definitions."""

    madrasa = models.ForeignKey(Madrasa, on_delete=models.CASCADE, related_name="rbac_roles")
    name = models.CharField(max_length=120)
    name_ur = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    legacy_key = models.CharField(max_length=30, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    permissions = models.ManyToManyField(PermissionDefinition, through="RolePermission", related_name="tenant_roles")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="rbac_roles_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_system", "name"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "slug"], name="unique_tenant_role_slug"),
            models.UniqueConstraint(fields=["madrasa", "legacy_key"], condition=~models.Q(legacy_key=""), name="unique_tenant_legacy_role"),
        ]

    def __str__(self):
        return f"{self.madrasa}: {self.name}"


class RolePermission(models.Model):
    role = models.ForeignKey(TenantRole, on_delete=models.CASCADE, related_name="permission_grants")
    permission = models.ForeignKey(PermissionDefinition, on_delete=models.CASCADE, related_name="role_grants")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission")]


class UserRoleAssignment(models.Model):
    madrasa = models.ForeignKey(Madrasa, on_delete=models.CASCADE, related_name="rbac_assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rbac_assignments")
    role = models.ForeignKey(TenantRole, on_delete=models.PROTECT, related_name="user_assignments")
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="rbac_assignments_created")
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="rbac_assignments_revoked")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user_id", "role__name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "user", "role"], name="unique_user_tenant_role")]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.role_id and self.madrasa_id != self.role.madrasa_id:
            raise ValidationError("The role must belong to the assignment madrasa.")
        profile = getattr(self.user, "profile", None) if self.user_id else None
        if profile and profile.madrasa_id != self.madrasa_id:
            raise ValidationError("The user must belong to the assignment madrasa.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} — {self.role}"


class MadrasaProfile(models.Model):
    """Tenant-specific institution profile used throughout the system."""

    class StudentTerminology(models.TextChoices):
        BOYS = "boys", "طلبہ"
        GIRLS = "girls", "طالبات"
        MIXED = "mixed", "طلبہ و طالبات"

    DEFAULT_PRIMARY_COLOR = "#226CE0"
    DEFAULT_SIDEBAR_COLOR = "#172554"

    madrasa = models.OneToOneField(Madrasa, on_delete=models.CASCADE, related_name="profile", null=True, blank=True)
    name = models.CharField(max_length=250, blank=True)
    name_english = models.CharField(max_length=250, blank=True)
    logo = models.ImageField(upload_to="madrasa/logo/", blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True, default="Pakistan")
    postal_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    alternate_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    principal_name = models.CharField(max_length=200, blank=True)
    principal_title = models.CharField(max_length=120, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    established_year = models.PositiveIntegerField(blank=True, null=True)
    primary_color = models.CharField(max_length=7, default=DEFAULT_PRIMARY_COLOR)
    sidebar_color = models.CharField(max_length=7, default=DEFAULT_SIDEBAR_COLOR)
    student_terminology = models.CharField(max_length=10, choices=StudentTerminology.choices, default=StudentTerminology.BOYS)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Madrasa profile"
        verbose_name_plural = "Madrasa profile"

    def __str__(self):
        return self.name or "Madrasa profile"
