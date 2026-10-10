from rest_framework.routers import DefaultRouter
from .views import ArchiveBatchViewSet,ArchivePolicyViewSet,AuditDashboardViewSet,AuditEventViewSet,LegalHoldViewSet
router=DefaultRouter()
router.register("audit/events",AuditEventViewSet,basename="audit-event")
router.register("audit/archive-policies",ArchivePolicyViewSet,basename="archive-policy")
router.register("audit/archive-batches",ArchiveBatchViewSet,basename="archive-batch")
router.register("audit/legal-holds",LegalHoldViewSet,basename="legal-hold")
router.register("audit/dashboard",AuditDashboardViewSet,basename="audit-dashboard")
urlpatterns=router.urls
