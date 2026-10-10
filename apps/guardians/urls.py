from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import GuardianActivationAPIView, GuardianAnnouncementViewSet, GuardianManagementViewSet, ParentMeetingBookingViewSet, ParentMeetingSlotViewSet, ParentPortalAPIView

router = DefaultRouter()
router.register("guardians/manage", GuardianManagementViewSet, basename="guardian-management")
router.register("guardians/meeting-slots", ParentMeetingSlotViewSet, basename="parent-meeting-slot")
router.register("guardians/meeting-bookings", ParentMeetingBookingViewSet, basename="parent-meeting-booking")
router.register("guardians/announcements", GuardianAnnouncementViewSet, basename="guardian-announcement")

urlpatterns = [
    path("guardians/activate/<str:token>/", GuardianActivationAPIView.as_view(), name="guardian-activate"),
    path("guardians/portal/", ParentPortalAPIView.as_view(), name="guardian-portal"),
] + router.urls
