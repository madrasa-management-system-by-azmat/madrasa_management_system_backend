from rest_framework.routers import DefaultRouter

from .views import (
	AcademicClassViewSet,
	AcademicYearViewSet,
	AdmissionApplicationViewSet,
	AttendanceAlertViewSet,
	AlumniProfileViewSet,
	DepartmentViewSet,
	GraduationRecordViewSet,
	HalaqaViewSet,
	PromotionDecisionViewSet,
	StudentAttendanceViewSet,
	StudentEnrollmentViewSet,
	StudentViewSet,
)


router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("classes", AcademicClassViewSet, basename="academic-class")
router.register("halaqas", HalaqaViewSet, basename="halaqa")
router.register("students", StudentViewSet, basename="student")
router.register("student-attendance", StudentAttendanceViewSet, basename="student-attendance")
router.register("attendance-alerts", AttendanceAlertViewSet, basename="attendance-alert")
router.register("academic-years", AcademicYearViewSet, basename="academic-year")
router.register("student-enrollments", StudentEnrollmentViewSet, basename="student-enrollment")
router.register("admission-applications", AdmissionApplicationViewSet, basename="admission-application")
router.register("promotion-decisions", PromotionDecisionViewSet, basename="promotion-decision")
router.register("graduation-records", GraduationRecordViewSet, basename="graduation-record")
router.register("alumni", AlumniProfileViewSet, basename="alumni-profile")

urlpatterns = router.urls
