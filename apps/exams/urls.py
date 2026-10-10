from rest_framework.routers import DefaultRouter

from .views import AnnualResultViewSet, ExamAttendanceViewSet, ExamDutyViewSet, InternalExamResultViewSet, InternalExamViewSet, WafaqBoardRegistrationViewSet, WafaqResultViewSet

router = DefaultRouter()
router.register("internal-exams", InternalExamViewSet, basename="internal-exam")
router.register("internal-exam-results", InternalExamResultViewSet, basename="internal-exam-result")
router.register("wafaq-registrations", WafaqBoardRegistrationViewSet, basename="wafaq-registration")
router.register("wafaq-results", WafaqResultViewSet, basename="wafaq-result")
router.register("exam-duties", ExamDutyViewSet, basename="exam-duty")
router.register("exam-attendance", ExamAttendanceViewSet, basename="exam-attendance")
router.register("annual-results", AnnualResultViewSet, basename="annual-result")

urlpatterns = router.urls
