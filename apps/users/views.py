from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from .models import Madrasa, MadrasaProfile, UserProfile
from .serializers import ChangePasswordSerializer, CreateMadrasaSerializer, CreateMadrasaUserSerializer, LoginSerializer, LogoutSerializer, MadrasaProfileSerializer, MadrasaUserSerializer, RegisterSerializer, SuperAdminMadrasaDetailSerializer, UpdateUserSerializer, UserSerializer
from .tenancy import current_madrasa
from .backup import create_backup, restore_backup

User = get_user_model()


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
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
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
        if request.user.profile.role != UserProfile.Role.ADMIN:
            return None
        return current_madrasa(request)

    def get(self, request):
        tenant = self._tenant_admin(request)
        if not tenant:
            return Response({"detail": "Only madrasa admins can create backups."}, status=status.HTTP_403_FORBIDDEN)
        output = create_backup(tenant)
        filename = f"{tenant.slug}-backup-{timezone.localdate().isoformat()}.zip"
        return FileResponse(output, as_attachment=True, filename=filename, content_type="application/zip")

    def post(self, request):
        tenant = self._tenant_admin(request)
        if not tenant:
            return Response({"detail": "Only madrasa admins can restore backups."}, status=status.HTTP_403_FORBIDDEN)
        archive = request.FILES.get("backup")
        if not archive:
            return Response({"backup": ["A backup ZIP file is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = restore_backup(archive, tenant)
        except ValidationError as error:
            return Response({"backup": error.detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Backup restored successfully.", **result})


class MadrasaUserManagementAPIView(APIView):
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
        return Response(UserSerializer(user).data)


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
        return Response({"detail": "Password changed. Please log in again."})


class JwtTokenRefreshAPIView(TokenRefreshView):
    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class JwtTokenVerifyAPIView(TokenVerifyView):
    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
