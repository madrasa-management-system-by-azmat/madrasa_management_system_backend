from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BackupRunViewSet, BackupScheduleAPIView

router = DefaultRouter()
router.register("backups", BackupRunViewSet, basename="backup-run")

urlpatterns = [path("backups/config/", BackupScheduleAPIView.as_view(), name="backup-schedule")]
urlpatterns += router.urls
