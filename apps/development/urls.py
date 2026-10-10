from rest_framework.routers import DefaultRouter
from .views import AlumniEngagementViewSet, DevelopmentDashboardViewSet, DisciplineActionViewSet, DisciplineAppealViewSet, DisciplineCategoryViewSet, DisciplineIncidentViewSet, RewardCategoryViewSet, RewardNominationViewSet, TrainingEnrollmentViewSet, TrainingProgramViewSet
router=DefaultRouter()
router.register("development/discipline-categories",DisciplineCategoryViewSet,basename="discipline-category")
router.register("development/incidents",DisciplineIncidentViewSet,basename="discipline-incident")
router.register("development/discipline-actions",DisciplineActionViewSet,basename="discipline-action")
router.register("development/discipline-appeals",DisciplineAppealViewSet,basename="discipline-appeal")
router.register("development/training-programs",TrainingProgramViewSet,basename="training-program")
router.register("development/training-enrollments",TrainingEnrollmentViewSet,basename="training-enrollment")
router.register("development/reward-categories",RewardCategoryViewSet,basename="reward-category")
router.register("development/rewards",RewardNominationViewSet,basename="reward-nomination")
router.register("development/alumni-engagements",AlumniEngagementViewSet,basename="alumni-engagement")
router.register("development/dashboard",DevelopmentDashboardViewSet,basename="development-dashboard")
urlpatterns=router.urls
