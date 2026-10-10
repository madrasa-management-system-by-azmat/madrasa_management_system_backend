import logging

from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .models import Madrasa, MadrasaProfile, PermissionDefinition, TenantRole, UserProfile, UserRoleAssignment
from .serializers import ChangePasswordSerializer, CreateMadrasaSerializer, CreateMadrasaUserSerializer, LoginSerializer, LogoutSerializer, MadrasaProfileSerializer, MadrasaUserSerializer, PermissionDefinitionSerializer, RegisterSerializer, SuperAdminMadrasaDetailSerializer, TenantRoleSerializer, UpdateUserSerializer, UserSerializer
from .tenancy import current_madrasa
from .backup import create_backup, restore_backup
from apps.auditlog.services import audit_event
from .permissions import HasPermissionCode
from .rbac import ensure_tenant_system_roles, sync_legacy_assignment, user_has_permission

User = get_user_model()
logger = logging.getLogger(__name__)


class IsPlatformSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def jwt_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Authentication"], request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        return Response({"detail": "Public registration is disabled. Contact the madrasa administrator."}, status=status.HTTP_403_FORBIDDEN)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Authentication"], request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            audit_event(category="auth", action="login_failed", metadata={"identifier": request.data.get("identifier", "")})
            raise ValidationError(serializer.errors)
        user = serializer.validated_data["user"]
        profile = getattr(user, "profile", None)
        if not user.is_superuser and (not profile or not profile.madrasa_id or not profile.madrasa.is_active):
            audit_event(category="auth", action="login_denied", actor=user, madrasa=getattr(profile, "madrasa", None), metadata={"reason": "inactive_membership"})
            return Response({"detail": "This madrasa account is inactive."}, status=status.HTTP_403_FORBIDDEN)
        audit_event(category="auth", action="login_success", actor=user, madrasa=getattr(profile, "madrasa", None))
        return Response(jwt_response(user))


class MeAPIView(APIView):
    @extend_schema(tags=["Authentication"], responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(tags=["Authentication"], request=UpdateUserSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = UpdateUserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class MadrasaProfileAPIView(APIView):
    def check_permissions(self, request):
        super().check_permissions(request)
        required = "settings.view" if request.method == "GET" else "settings.manage"
        if not user_has_permission(request.user, required):
            self.permission_denied(request, message="You do not have permission to access madrasa settings.")

    @extend_schema(tags=["Settings"], responses=MadrasaProfileSerializer)
    def get(self, request):
        profile, _ = MadrasaProfile.objects.get_or_create(madrasa=current_madrasa(request), defaults={"name": current_madrasa(request).name})
        return Response(MadrasaProfileSerializer(profile, context={"request": request}).data)

    @extend_schema(tags=["Settings"], request=MadrasaProfileSerializer, responses=MadrasaProfileSerializer)
    def put(self, request):
        if request.user.profile.role != UserProfile.Role.ADMIN:
            return Response({"detail": "Only madrasa admins can update madrasa details."}, status=status.HTTP_403_FORBIDDEN)
        profile, _ = MadrasaProfile.objects.get_or_create(madrasa=current_madrasa(request), defaults={"name": current_madrasa(request).name})
        serializer = MadrasaProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class TenantBackupAPIView(APIView):
    """Admin-only tenant backup download and destructive restore endpoint."""

    def _tenant_admin(self, request):
        return current_madrasa(request)

    def get(self, request):
        tenant = self._tenant_admin(request)
        if not tenant:
            return Response({"detail": "Only madrasa admins can create backups."}, status=status.HTTP_403_FORBIDDEN)
        if not user_has_permission(request.user, "settings.backup"):
            return Response({"detail": "You do not have backup permission."}, status=status.HTTP_403_FORBIDDEN)
        output = create_backup(tenant)
        audit_event(category="backup", action="backup_download", madrasa=tenant, actor=request.user)
        filename = f"{tenant.slug}-backup-{timezone.localdate().isoformat()}.zip"
        return FileResponse(output, as_attachment=True, filename=filename, content_type="application/zip")

    def post(self, request):
        tenant = self._tenant_admin(request)
        if not tenant:
            return Response({"detail": "Only madrasa admins can restore backups."}, status=status.HTTP_403_FORBIDDEN)
        if not user_has_permission(request.user, "settings.restore"):
            return Response({"detail": "You do not have restore permission."}, status=status.HTTP_403_FORBIDDEN)
        archive = request.FILES.get("backup")
        if not archive:
            return Response({"backup": ["A backup ZIP file is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            audit_event(category="restore", action="restore_started", madrasa=tenant, actor=request.user, metadata={"filename": archive.name})
            result = restore_backup(archive, tenant)
        except ValidationError as error:
            audit_event(category="restore", action="restore_failed", madrasa=tenant, actor=request.user, metadata={"filename": archive.name, "reason": str(error.detail)})
            return Response({"backup": error.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Tenant backup restore failed for madrasa %s", tenant.pk)
            audit_event(category="restore", action="restore_failed", madrasa=tenant, actor=request.user, metadata={"filename": archive.name, "reason": "unexpected_error"})
            return Response(
                {"backup": ["The backup could not be restored. Verify the file and try again."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        audit_event(category="restore", action="restore_succeeded", madrasa=tenant, actor=request.user, metadata=result)
        return Response({"detail": "Backup restored successfully.", **result})


class MadrasaUserManagementAPIView(APIView):
    def check_permissions(self, request):
        super().check_permissions(request)
        code = "users.view" if request.method == "GET" else "users.manage"
        if not user_has_permission(request.user, code):
            self.permission_denied(request, message="You do not have permission to manage users.")

    def get(self, request):
        tenant = current_madrasa(request)
        if request.user.profile.role != UserProfile.Role.ADMIN:
            return Response({"detail": "Only madrasa admins can manage users."}, status=status.HTTP_403_FORBIDDEN)
        users = User.objects.filter(profile__madrasa=tenant).select_related("profile")
        return Response(MadrasaUserSerializer(users, many=True, context={"request": request}).data)

    def post(self, request):
        if request.user.profile.role != UserProfile.Role.ADMIN:
            return Response({"detail": "Only madrasa admins can create users."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CreateMadrasaUserSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)

    def patch(self, request, user_id):
        tenant = current_madrasa(request)
        if request.user.profile.role != UserProfile.Role.ADMIN:
            return Response({"detail": "Only madrasa admins can manage users."}, status=status.HTTP_403_FORBIDDEN)
        user = User.objects.filter(pk=user_id, profile__madrasa=tenant).select_related("profile").first()
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if user == request.user and any(key in request.data for key in ("role", "email")):
            return Response({"detail": "You cannot change your own role or email."}, status=status.HTTP_400_BAD_REQUEST)
        for field in ("first_name", "last_name"):
            if field in request.data:
                setattr(user, field, request.data[field])
        if "is_active" in request.data:
            user.is_active = bool(request.data["is_active"])
        if "email" in request.data and user != request.user:
            user.email = request.data["email"]
        user.save()
        if "role" in request.data and user != request.user:
            if request.data["role"] not in UserProfile.Role.values:
                return Response({"role": ["Invalid role."]}, status=status.HTTP_400_BAD_REQUEST)
            user.profile.role = request.data["role"]
            user.profile.save(update_fields=["role"])
            sync_legacy_assignment(user.profile, assigned_by=request.user)
        if "role_ids" in request.data and user != request.user:
            role_ids = request.data.get("role_ids") or []
            roles = list(TenantRole.objects.filter(madrasa=tenant, pk__in=role_ids, is_active=True))
            if len(roles) != len(set(role_ids)):
                return Response({"role_ids": ["One or more roles are invalid."]}, status=status.HTTP_400_BAD_REQUEST)
            UserRoleAssignment.objects.filter(madrasa=tenant, user=user).update(is_active=False, revoked_by=request.user, revoked_at=timezone.now())
            for role in roles:
                UserRoleAssignment.objects.update_or_create(madrasa=tenant, user=user, role=role, defaults={"is_active": True, "assigned_by": request.user, "revoked_by": None, "revoked_at": None, "expires_at": None})
        audit_event(category="security", action="user_permissions_updated", madrasa=tenant, actor=request.user, entity_type="auth.user", entity_id=str(user.pk), entity_label=user.username, metadata={"role_ids": request.data.get("role_ids"), "legacy_role": request.data.get("role")})
        return Response(UserSerializer(user).data)


class PermissionCatalogueAPIView(APIView):
    permission_classes = [HasPermissionCode]
    required_permission = "roles.view"

    def get(self, request):
        return Response(PermissionDefinitionSerializer(PermissionDefinition.objects.filter(is_active=True), many=True).data)


class TenantRoleViewSet(viewsets.ModelViewSet):
    serializer_class = TenantRoleSerializer
    permission_classes = [HasPermissionCode]
    action_permissions = {"list": "roles.view", "retrieve": "roles.view", "create": "roles.manage", "update": "roles.manage", "partial_update": "roles.manage", "destroy": "roles.manage"}

    def get_queryset(self):
        tenant = current_madrasa(self.request)
        ensure_tenant_system_roles(tenant)
        return TenantRole.objects.filter(madrasa=tenant).prefetch_related("permissions")

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError("System roles cannot be deleted.")
        if instance.user_assignments.filter(is_active=True).exists():
            raise ValidationError("Remove this role from all users before deleting it.")
        instance.delete()


class SuperAdminMadrasaAPIView(APIView):
    permission_classes = [IsPlatformSuperAdmin]

    def get(self, request):
        return Response(SuperAdminMadrasaDetailSerializer(Madrasa.objects.select_related("profile"), many=True).data)

    def post(self, request):
        serializer = CreateMadrasaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        return Response(SuperAdminMadrasaDetailSerializer(tenant).data, status=status.HTTP_201_CREATED)


class SuperAdminMadrasaDetailAPIView(APIView):
    permission_classes = [IsPlatformSuperAdmin]

    def patch(self, request, madrasa_id):
        madrasa = Madrasa.objects.filter(pk=madrasa_id).select_related("profile").first()
        if not madrasa:
            return Response({"detail": "Madrasa not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SuperAdminMadrasaDetailSerializer(madrasa, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SuperAdminMadrasaDetailSerializer(madrasa).data)

    def post(self, request, madrasa_id):
        madrasa = Madrasa.objects.filter(pk=madrasa_id).first()
        if not madrasa:
            return Response({"detail": "Madrasa not found."}, status=status.HTTP_404_NOT_FOUND)
        password = request.data.get("password")
        if not password or len(password) < 8:
            return Response({"password": ["Password must contain at least 8 characters."]}, status=status.HTTP_400_BAD_REQUEST)
        admin_profile = UserProfile.objects.filter(madrasa=madrasa, role=UserProfile.Role.ADMIN).select_related("user").first()
        if not admin_profile:
            return Response({"detail": "No madrasa admin is assigned."}, status=status.HTTP_404_NOT_FOUND)
        admin_profile.user.set_password(password)
        admin_profile.user.save(update_fields=["password"])
        return Response({"detail": "Madrasa admin password has been reset."})


class LogoutAPIView(APIView):
    @extend_schema(tags=["Authentication"], request=LogoutSerializer, responses={204: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except Exception:
            return Response({"detail": "Refresh token is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        audit_event(category="auth", action="logout", actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordAPIView(APIView):
    @extend_schema(tags=["Authentication"], request=ChangePasswordSerializer, responses={200: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        for token in OutstandingToken.objects.filter(user=request.user):
            BlacklistedToken.objects.get_or_create(token=token)
        audit_event(category="security", action="password_changed", actor=request.user)
        return Response({"detail": "Password changed. Please log in again."})


class JwtTokenRefreshAPIView(TokenRefreshView):
    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class JwtTokenVerifyAPIView(TokenVerifyView):
    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
