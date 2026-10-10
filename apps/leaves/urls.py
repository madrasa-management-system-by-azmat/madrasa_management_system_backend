from rest_framework.routers import DefaultRouter

from .views import InstitutionCalendarDayViewSet, LeaveAttachmentViewSet, LeaveBalanceViewSet, LeaveDashboardViewSet, LeavePolicyRuleViewSet, LeavePolicyViewSet, LeaveRequestViewSet, LeaveSubstitutionViewSet, LeaveTypeViewSet

router = DefaultRouter()
router.register("leaves/calendar", InstitutionCalendarDayViewSet, basename="leave-calendar")
router.register("leaves/types", LeaveTypeViewSet, basename="leave-type")
router.register("leaves/policies", LeavePolicyViewSet, basename="leave-policy")
router.register("leaves/policy-rules", LeavePolicyRuleViewSet, basename="leave-policy-rule")
router.register("leaves/balances", LeaveBalanceViewSet, basename="leave-balance")
router.register("leaves/requests", LeaveRequestViewSet, basename="leave-request")
router.register("leaves/substitutions", LeaveSubstitutionViewSet, basename="leave-substitution")
router.register("leaves/attachments", LeaveAttachmentViewSet, basename="leave-attachment")
router.register("leaves/dashboard", LeaveDashboardViewSet, basename="leave-dashboard")

urlpatterns = router.urls
