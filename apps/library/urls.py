from rest_framework.routers import DefaultRouter

from .views import LibraryBookCopyViewSet, LibraryBookViewSet, LibraryCategoryViewSet, LibraryDashboardViewSet, LibraryFineViewSet, LibraryLoanViewSet, LibraryMemberViewSet, LibraryReservationViewSet, LibraryShelfViewSet

router = DefaultRouter()
router.register("library/categories", LibraryCategoryViewSet, basename="library-category")
router.register("library/shelves", LibraryShelfViewSet, basename="library-shelf")
router.register("library/books", LibraryBookViewSet, basename="library-book")
router.register("library/copies", LibraryBookCopyViewSet, basename="library-copy")
router.register("library/members", LibraryMemberViewSet, basename="library-member")
router.register("library/loans", LibraryLoanViewSet, basename="library-loan")
router.register("library/fines", LibraryFineViewSet, basename="library-fine")
router.register("library/reservations", LibraryReservationViewSet, basename="library-reservation")
router.register("library/dashboard", LibraryDashboardViewSet, basename="library-dashboard")

urlpatterns = router.urls
