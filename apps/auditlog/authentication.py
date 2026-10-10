from rest_framework_simplejwt.authentication import JWTAuthentication


class AuditJWTAuthentication(JWTAuthentication):
    """JWT authentication that exposes the resolved actor to audit middleware/signals."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, token = result
            underlying_request = getattr(request, "_request", request)
            underlying_request.user = user
            return user, token
        return None
