from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from .models import Madrasa, MadrasaProfile, UserProfile

User = get_user_model()


class MadrasaProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MadrasaProfile
        fields = [
            "id", "name", "name_english", "logo", "address", "city", "province",
            "country", "postal_code", "phone", "alternate_phone", "email", "website",
            "principal_name", "principal_title", "registration_number", "established_year",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    madrasa_id = serializers.SerializerMethodField()
    madrasa_name = serializers.SerializerMethodField()
    is_super_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "phone", "photo", "madrasa_id", "madrasa_name", "is_super_admin"]

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

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "phone", "photo", "is_active"]
        read_only_fields = ["id", "email"]


class CreateMadrasaUserSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=UserProfile.Role.choices)

    def create(self, validated_data):
        tenant = self.context["request"].user.profile.madrasa
        role = validated_data.pop("role")
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, madrasa=tenant, role=role, phone=phone)
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
        UserProfile.objects.create(user=user, madrasa=tenant, role=UserProfile.Role.ADMIN)
        MadrasaProfile.objects.create(madrasa=tenant, name=tenant.name)
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
            profile = UserProfile.objects.select_related("user").filter(phone=identifier).first()
            user = profile.user if profile else None

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
