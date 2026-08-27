from rest_framework.routers import DefaultRouter

from .views import GatePassViewSet, HostelAllocationViewSet, HostelRoomViewSet, HostelWingViewSet

router = DefaultRouter()
router.register("hostel-wings", HostelWingViewSet, basename="hostel-wing")
router.register("hostel-rooms", HostelRoomViewSet, basename="hostel-room")
router.register("hostel-allocations", HostelAllocationViewSet, basename="hostel-allocation")
router.register("gate-passes", GatePassViewSet, basename="gate-pass")

urlpatterns = router.urls
