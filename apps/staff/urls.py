from rest_framework.routers import DefaultRouter

from .views import HalaqaAssignmentViewSet, StaffAttendanceViewSet, StaffViewSet

router = DefaultRouter()
router.register("staff", StaffViewSet, basename="staff")
router.register("staff-attendance", StaffAttendanceViewSet, basename="staff-attendance")
router.register("halaqa-assignments", HalaqaAssignmentViewSet, basename="halaqa-assignment")

urlpatterns = router.urls
