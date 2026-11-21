from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CertificateDashboardViewSet,
    CertificateTemplateViewSet,
    CertificateViewSet,
    PublicCertificateVerificationAPIView,
)

router = DefaultRouter()
router.register("certificates/templates", CertificateTemplateViewSet, basename="certificate-template")
router.register("certificates/records", CertificateViewSet, basename="certificate")
router.register("certificates/dashboard", CertificateDashboardViewSet, basename="certificate-dashboard")

urlpatterns = [
    path("certificates/public/verify/<uuid:public_id>/", PublicCertificateVerificationAPIView.as_view(), name="public-certificate-verify"),
] + router.urls
