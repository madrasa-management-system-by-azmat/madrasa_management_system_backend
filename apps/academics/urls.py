from rest_framework.routers import DefaultRouter

from .views import (
	ClassOfferingViewSet,
	CurriculumBookViewSet,
	CurriculumPlanViewSet,
	CurriculumUnitViewSet,
	DailyLessonViewSet,
	SubjectViewSet,
	TimetableEntryViewSet,
	TimetablePeriodViewSet,
)

router = DefaultRouter()
router.register("subjects", SubjectViewSet, basename="subject")
router.register("class-offerings", ClassOfferingViewSet, basename="class-offering")
router.register("curriculum-plans", CurriculumPlanViewSet, basename="curriculum-plan")
router.register("curriculum-books", CurriculumBookViewSet, basename="curriculum-book")
router.register("curriculum-units", CurriculumUnitViewSet, basename="curriculum-unit")
router.register("timetable-periods", TimetablePeriodViewSet, basename="timetable-period")
router.register("timetable-entries", TimetableEntryViewSet, basename="timetable-entry")
router.register("daily-lessons", DailyLessonViewSet, basename="daily-lesson")

urlpatterns = router.urls
