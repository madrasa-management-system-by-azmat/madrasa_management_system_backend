from rest_framework.routers import DefaultRouter

from .views import HifzDailyLogViewSet

router = DefaultRouter()
router.register("hifz-daily-logs", HifzDailyLogViewSet, basename="hifz-daily-log")

urlpatterns = router.urls
