from rest_framework.routers import DefaultRouter

from .views import DocumentAccessGrantViewSet, DocumentCategoryViewSet, DocumentCommentViewSet, DocumentDashboardViewSet, DocumentFolderViewSet, DocumentLinkViewSet, DocumentVersionViewSet, DocumentViewSet

router = DefaultRouter()
router.register("documents/categories", DocumentCategoryViewSet, basename="document-category")
router.register("documents/folders", DocumentFolderViewSet, basename="document-folder")
router.register("documents/records", DocumentViewSet, basename="document")
router.register("documents/versions", DocumentVersionViewSet, basename="document-version")
router.register("documents/access", DocumentAccessGrantViewSet, basename="document-access")
router.register("documents/links", DocumentLinkViewSet, basename="document-link")
router.register("documents/comments", DocumentCommentViewSet, basename="document-comment")
router.register("documents/dashboard", DocumentDashboardViewSet, basename="document-dashboard")

urlpatterns = router.urls
