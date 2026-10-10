from rest_framework.routers import DefaultRouter

from .views import MeetingActionItemViewSet, MeetingAgendaItemViewSet, MeetingAttachmentViewSet, MeetingDashboardViewSet, MeetingDecisionViewSet, MeetingMinutesRevisionViewSet, MeetingParticipantViewSet, MeetingTypeViewSet, MeetingViewSet

router = DefaultRouter()
router.register("meetings/types", MeetingTypeViewSet, basename="meeting-type")
router.register("meetings/records", MeetingViewSet, basename="meeting")
router.register("meetings/agenda", MeetingAgendaItemViewSet, basename="meeting-agenda")
router.register("meetings/participants", MeetingParticipantViewSet, basename="meeting-participant")
router.register("meetings/minutes", MeetingMinutesRevisionViewSet, basename="meeting-minutes")
router.register("meetings/decisions", MeetingDecisionViewSet, basename="meeting-decision")
router.register("meetings/actions", MeetingActionItemViewSet, basename="meeting-action")
router.register("meetings/attachments", MeetingAttachmentViewSet, basename="meeting-attachment")
router.register("meetings/dashboard", MeetingDashboardViewSet, basename="meeting-dashboard")

urlpatterns = router.urls
