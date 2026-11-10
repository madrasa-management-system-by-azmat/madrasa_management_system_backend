from rest_framework.routers import DefaultRouter

from .views import (
    DutyAssignmentViewSet,
    DutyCategoryViewSet,
    GuestInvitationViewSet,
    TaqreebViewSet,
)

router = DefaultRouter()
router.register(r"taqreeb/events", TaqreebViewSet, basename="taqreeb-events")
router.register(r"taqreeb/categories", DutyCategoryViewSet, basename="taqreeb-categories")
router.register(r"taqreeb/duties", DutyAssignmentViewSet, basename="taqreeb-duties")
router.register(r"taqreeb/invitations", GuestInvitationViewSet, basename="taqreeb-invitations")

urlpatterns = router.urls

