from rest_framework.routers import DefaultRouter

from .views import (
	HalaqaAssignmentViewSet,
	PerformanceGoalViewSet,
	PerformanceReviewViewSet,
	StaffAttendanceViewSet,
	StaffContributionViewSet,
	StaffViewSet,
	SyllabusPlanViewSet,
	SyllabusProgressEntryViewSet,
	TeachingAssignmentViewSet,
)

router = DefaultRouter()
router.register("staff", StaffViewSet, basename="staff")
router.register("staff-attendance", StaffAttendanceViewSet, basename="staff-attendance")
router.register("halaqa-assignments", HalaqaAssignmentViewSet, basename="halaqa-assignment")
router.register("teaching-assignments", TeachingAssignmentViewSet, basename="teaching-assignment")
router.register("syllabus-plans", SyllabusPlanViewSet, basename="syllabus-plan")
router.register("syllabus-progress", SyllabusProgressEntryViewSet, basename="syllabus-progress")
router.register("staff-contributions", StaffContributionViewSet, basename="staff-contribution")
router.register("performance-reviews", PerformanceReviewViewSet, basename="performance-review")
router.register("performance-goals", PerformanceGoalViewSet, basename="performance-goal")

urlpatterns = router.urls
