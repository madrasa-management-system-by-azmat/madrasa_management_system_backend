from django.contrib.auth import authenticate, get_user_model
import re

from rest_framework import serializers

from .models import Madrasa, MadrasaProfile, PermissionDefinition, TenantRole, UserProfile, UserRoleAssignment
from .rbac import effective_permissions

User = get_user_model()


def assign_selected_roles(*, user, tenant, role_ids, assigned_by):
    roles = list(TenantRole.objects.filter(madrasa=tenant, pk__in=role_ids, is_active=True))
    if len(roles) != len(set(role_ids)):
        raise serializers.ValidationError({"role_ids": ["One or more roles are invalid."]})
    for tenant_role in roles:
        UserRoleAssignment.objects.create(madrasa=tenant, user=user, role=tenant_role, assigned_by=assigned_by)
    return roles


class MadrasaProfileSerializer(serializers.ModelSerializer):
    def validate_primary_color(self, value):
        return self._validate_hex_color(value)

    def validate_sidebar_color(self, value):
        return self._validate_hex_color(value)

    @staticmethod
    def _validate_hex_color(value):
        value = value.strip().upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", value):
            raise serializers.ValidationError("Enter a valid hex color, for example #226CE0.")
        return value

    class Meta:
        model = MadrasaProfile
        fields = [
            "id", "name", "name_english", "logo", "address", "city", "province",
            "country", "postal_code", "phone", "alternate_phone", "email", "website",
            "principal_name", "principal_title", "registration_number", "established_year",
            "primary_color", "sidebar_color", "student_terminology", "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    madrasa_id = serializers.SerializerMethodField()
    madrasa_name = serializers.SerializerMethodField()
    is_super_admin = serializers.BooleanField(source="is_superuser", read_only=True)
    permissions = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "roles", "permissions", "phone", "photo", "madrasa_id", "madrasa_name", "is_super_admin"]

    def get_profile(self, user):
        return getattr(user, "profile", None)

    def get_role(self, user):
        return "super_admin" if user.is_superuser else getattr(self.get_profile(user), "role", None)

    def get_phone(self, user):
        return getattr(self.get_profile(user), "phone", "")

    def get_photo(self, user):
        photo = getattr(self.get_profile(user), "photo", None)
        return photo.url if photo else None

    def get_madrasa_id(self, user):
        return getattr(self.get_profile(user), "madrasa_id", None)

    def get_madrasa_name(self, user):
        profile = self.get_profile(user)
        return profile.madrasa.name if profile and profile.madrasa_id else None

    def get_permissions(self, user):
        return sorted(effective_permissions(user))

    def get_roles(self, user):
        if user.is_superuser:
            return []
        return list(UserRoleAssignment.objects.filter(user=user, is_active=True, role__is_active=True).values("role_id", "role__slug", "role__name", "role__name_ur"))


class PermissionDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionDefinition
        fields = ["id", "code", "module", "action", "name", "description", "is_sensitive"]


class TenantRoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SlugRelatedField(source="permissions", slug_field="code", many=True, queryset=PermissionDefinition.objects.filter(is_active=True), required=False)
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = TenantRole
        fields = ["id", "name", "name_ur", "slug", "description", "legacy_key", "is_system", "is_active", "permission_codes", "user_count", "created_at", "updated_at"]
        read_only_fields = ["id", "legacy_key", "is_system", "created_at", "updated_at"]

    def get_user_count(self, role):
        return role.user_assignments.filter(is_active=True).count()

    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        role = TenantRole.objects.create(madrasa=self.context["request"].user.profile.madrasa, created_by=self.context["request"].user, **validated_data)
        role.permissions.set(permissions)
        return role

    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None)
        if instance.is_system:
            for protected in ("slug", "is_active"):
                validated_data.pop(protected, None)
        instance = super().update(instance, validated_data)
        if permissions is not None:
            instance.permissions.set(permissions)
        return instance


class UpdateUserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "photo"]

    def update(self, instance, validated_data):
        phone = validated_data.pop("phone", None)
        photo = validated_data.pop("photo", serializers.empty)
        instance = super().update(instance, validated_data)
        if phone is not None or photo is not serializers.empty:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            update_fields = []
            if phone is not None:
                profile.phone = phone
                update_fields.append("phone")
            if photo is not serializers.empty:
                profile.photo = photo
                update_fields.append("photo")
            profile.save(update_fields=update_fields)
        return instance


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["username", "password", "first_name", "last_name", "email", "phone"]

    def create(self, validated_data):
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, phone=phone)
        return user


class MadrasaUserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=UserProfile.Role.choices, source="profile.role")
    phone = serializers.CharField(source="profile.phone", required=False, allow_blank=True)
    photo = serializers.ImageField(source="profile.photo", read_only=True)
    role_ids = serializers.SerializerMethodField()
    role_names = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "role_ids", "role_names", "phone", "photo", "is_active"]
        read_only_fields = ["id", "email"]

    def get_assignments(self, user):
        return UserRoleAssignment.objects.filter(user=user, is_active=True, role__is_active=True).select_related("role")

    def get_role_ids(self, user):
        return [item.role_id for item in self.get_assignments(user)]

    def get_role_names(self, user):
        return [item.role.name_ur or item.role.name for item in self.get_assignments(user)]


class CreateMadrasaUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=UserProfile.Role.choices, required=False, default=UserProfile.Role.OPERATOR)
    role_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def create(self, validated_data):
        tenant = self.context["request"].user.profile.madrasa
        role = validated_data.pop("role")
        role_ids = validated_data.pop("role_ids", [])
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        profile = UserProfile.objects.create(user=user, madrasa=tenant, role=role, phone=phone)
        if role_ids:
            assign_selected_roles(user=user, tenant=tenant, role_ids=role_ids, assigned_by=self.context["request"].user)
        else:
            from .rbac import sync_legacy_assignment
            sync_legacy_assignment(profile, assigned_by=self.context["request"].user)
        return user


class CreateMadrasaSerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(write_only=True)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_email = serializers.EmailField(write_only=True)
    admin_first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    admin_last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Madrasa
        fields = ["id", "name", "slug", "is_active", "admin_username", "admin_password", "admin_email", "admin_first_name", "admin_last_name"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        admin = {key: validated_data.pop(key) for key in list(validated_data) if key.startswith("admin_")}
        tenant = Madrasa.objects.create(**validated_data)
        user = User.objects.create_user(username=admin["admin_username"], password=admin["admin_password"], email=admin["admin_email"], first_name=admin.get("admin_first_name", ""), last_name=admin.get("admin_last_name", ""))
        user_profile = UserProfile.objects.create(user=user, madrasa=tenant, role=UserProfile.Role.ADMIN)
        MadrasaProfile.objects.create(madrasa=tenant, name=tenant.name)
        from .rbac import sync_legacy_assignment
        sync_legacy_assignment(user_profile, assigned_by=user)
        return tenant


class SuperAdminMadrasaDetailSerializer(serializers.ModelSerializer):
    profile = MadrasaProfileSerializer(read_only=True)
    admin = serializers.SerializerMethodField()

    class Meta:
        model = Madrasa
        fields = ["id", "name", "slug", "is_active", "created_at", "profile", "admin"]
        read_only_fields = ["id", "slug", "created_at", "admin"]

    def get_admin(self, madrasa):
        admin_profile = UserProfile.objects.filter(madrasa=madrasa, role=UserProfile.Role.ADMIN).select_related("user").first()
        return UserSerializer(admin_profile.user).data if admin_profile else None

    def update(self, instance, validated_data):
        profile_data = self.initial_data.get("profile")
        instance = super().update(instance, validated_data)
        if profile_data is not None:
            profile, _ = MadrasaProfile.objects.get_or_create(madrasa=instance, defaults={"name": instance.name})
            profile_serializer = MadrasaProfileSerializer(profile, data=profile_data, partial=True)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()
        return instance


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        user = User.objects.filter(username=identifier).first()

        if not user:
            profiles = list(UserProfile.objects.select_related("user").filter(phone=identifier, user__is_active=True)[:2])
            user = profiles[0].user if len(profiles) == 1 else None

        user = authenticate(username=user.username, password=attrs["password"]) if user else None
        if not user:
            raise serializers.ValidationError("Invalid username/mobile number or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
