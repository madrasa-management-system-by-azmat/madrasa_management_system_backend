from rest_framework.routers import DefaultRouter

from .views import AcademicClassViewSet, DepartmentViewSet, HalaqaViewSet, StudentAttendanceViewSet, StudentViewSet


router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("classes", AcademicClassViewSet, basename="academic-class")
router.register("halaqas", HalaqaViewSet, basename="halaqa")
router.register("students", StudentViewSet, basename="student")
router.register("student-attendance", StudentAttendanceViewSet, basename="student-attendance")

urlpatterns = router.urls
