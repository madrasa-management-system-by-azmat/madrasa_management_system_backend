from django.urls import path

from .views import (
    ChangePasswordAPIView,
    JwtTokenRefreshAPIView,
    JwtTokenVerifyAPIView,
    LoginAPIView,
    LogoutAPIView,
    MadrasaProfileAPIView,
    TenantBackupAPIView,
    MadrasaUserManagementAPIView,
    MeAPIView,
    RegisterAPIView,
    SuperAdminMadrasaAPIView,
    SuperAdminMadrasaDetailAPIView,
)


urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="auth-register"),
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("token/refresh/", JwtTokenRefreshAPIView.as_view(), name="auth-token-refresh"),
    path("token/verify/", JwtTokenVerifyAPIView.as_view(), name="auth-token-verify"),
    path("me/", MeAPIView.as_view(), name="auth-me"),
    path("madrasa-profile/", MadrasaProfileAPIView.as_view(), name="madrasa-profile"),
    path("backup/", TenantBackupAPIView.as_view(), name="tenant-backup"),
    path("madrasa-users/", MadrasaUserManagementAPIView.as_view(), name="madrasa-users"),
    path("madrasa-users/<int:user_id>/", MadrasaUserManagementAPIView.as_view(), name="madrasa-user-detail"),
    path("madrasas/", SuperAdminMadrasaAPIView.as_view(), name="super-admin-madrasas"),
    path("madrasas/<int:madrasa_id>/", SuperAdminMadrasaDetailAPIView.as_view(), name="super-admin-madrasa-detail"),
    path("logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="auth-change-password"),
]
