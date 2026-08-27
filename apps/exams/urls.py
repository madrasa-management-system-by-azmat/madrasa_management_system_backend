from rest_framework.routers import DefaultRouter

from .views import InternalExamResultViewSet, InternalExamViewSet, WafaqBoardRegistrationViewSet, WafaqResultViewSet

router = DefaultRouter()
router.register("internal-exams", InternalExamViewSet, basename="internal-exam")
router.register("internal-exam-results", InternalExamResultViewSet, basename="internal-exam-result")
router.register("wafaq-registrations", WafaqBoardRegistrationViewSet, basename="wafaq-registration")
router.register("wafaq-results", WafaqResultViewSet, basename="wafaq-result")

urlpatterns = router.urls
