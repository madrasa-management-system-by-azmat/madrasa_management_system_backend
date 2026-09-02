from django.conf import settings
from django.db import models


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

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    madrasa = models.ForeignKey(Madrasa, on_delete=models.PROTECT, related_name="members", null=True, blank=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.OPERATOR)
    phone = models.CharField(max_length=20, blank=True)
    photo = models.ImageField(upload_to="users/photos/", blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class MadrasaProfile(models.Model):
    """Tenant-specific institution profile used throughout the system."""

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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Madrasa profile"
        verbose_name_plural = "Madrasa profile"

    def __str__(self):
        return self.name or "Madrasa profile"
