from rest_framework.routers import DefaultRouter
from django.urls import path
from .scan_views import StudentScannerAPIView
from .attendance_daily import DailyAttendanceAPIView, ManualAttendanceEventsAPIView

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

urlpatterns = [
	path("student-attendance/scanner/", StudentScannerAPIView.as_view(), name="student-attendance-scanner"),
	path("student-attendance/daily/", DailyAttendanceAPIView.as_view(), name="student-attendance-daily"),
	path("student-attendance/manual-events/", ManualAttendanceEventsAPIView.as_view(), name="student-attendance-manual-events"),
] + router.urls
