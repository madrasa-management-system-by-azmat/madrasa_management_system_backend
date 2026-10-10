from rest_framework.routers import DefaultRouter

from .views import FatwaAttachmentViewSet, FatwaCategoryViewSet, FatwaDashboardViewSet, FatwaInquiryViewSet, FatwaPublicationViewSet, FatwaReferenceViewSet, FatwaRevisionViewSet, FatwaTagViewSet

router = DefaultRouter()
router.register("fatwas/categories", FatwaCategoryViewSet, basename="fatwa-category")
router.register("fatwas/tags", FatwaTagViewSet, basename="fatwa-tag")
router.register("fatwas/inquiries", FatwaInquiryViewSet, basename="fatwa-inquiry")
router.register("fatwas/revisions", FatwaRevisionViewSet, basename="fatwa-revision")
router.register("fatwas/references", FatwaReferenceViewSet, basename="fatwa-reference")
router.register("fatwas/attachments", FatwaAttachmentViewSet, basename="fatwa-attachment")
router.register("fatwas/publications", FatwaPublicationViewSet, basename="fatwa-publication")
router.register("fatwas/dashboard", FatwaDashboardViewSet, basename="fatwa-dashboard")

urlpatterns = router.urls
