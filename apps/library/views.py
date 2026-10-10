from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.users.rbac import user_has_permission

from apps.users.tenancy import TenantScopedViewSetMixin

from .models import LibraryBook, LibraryBookCopy, LibraryCategory, LibraryFine, LibraryLoan, LibraryMember, LibraryReservation, LibraryShelf
from .serializers import LibraryBookCopySerializer, LibraryBookSerializer, LibraryCategorySerializer, LibraryFineSerializer, LibraryLoanSerializer, LibraryMemberSerializer, LibraryReservationSerializer, LibraryShelfSerializer


class LibraryViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


@extend_schema(tags=["Library"])
class LibraryCategoryViewSet(LibraryViewSet):
    queryset = LibraryCategory.objects.annotate(book_total=Count("books"))
    serializer_class = LibraryCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name"]


@extend_schema(tags=["Library"])
class LibraryShelfViewSet(LibraryViewSet):
    queryset = LibraryShelf.objects.all()
    serializer_class = LibraryShelfSerializer
    search_fields = ["name", "code", "location"]
    ordering_fields = ["code", "name"]


@extend_schema(tags=["Library"])
class LibraryBookViewSet(LibraryViewSet):
    queryset = LibraryBook.objects.select_related("category").prefetch_related("copies__shelf")
    serializer_class = LibraryBookSerializer
    search_fields = ["title", "author", "isbn", "publisher"]
    ordering_fields = ["title", "author", "publication_year", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        category = self.request.query_params.get("category")
        availability = self.request.query_params.get("availability")
        language = self.request.query_params.get("language")
        if category:
            queryset = queryset.filter(category_id=category)
        if language:
            queryset = queryset.filter(language=language)
        if availability == "available":
            queryset = queryset.filter(copies__status=LibraryBookCopy.Status.AVAILABLE).distinct()
        return queryset


@extend_schema(tags=["Library"])
class LibraryBookCopyViewSet(LibraryViewSet):
    queryset = LibraryBookCopy.objects.select_related("book", "shelf")
    serializer_class = LibraryBookCopySerializer
    search_fields = ["accession_number", "barcode", "book__title", "book__author"]
    ordering_fields = ["accession_number", "status", "acquisition_date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        book = self.request.query_params.get("book")
        copy_status = self.request.query_params.get("status")
        if book:
            queryset = queryset.filter(book_id=book)
        if copy_status:
            queryset = queryset.filter(status=copy_status)
        return queryset

    def perform_destroy(self, instance):
        if instance.loans.exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Copies with circulation history cannot be deleted.")
        super().perform_destroy(instance)


@extend_schema(tags=["Library"])
class LibraryMemberViewSet(LibraryViewSet):
    queryset = LibraryMember.objects.select_related("student", "staff")
    serializer_class = LibraryMemberSerializer
    search_fields = ["membership_number", "student__full_name", "student__registration_number", "staff__full_name", "external_name", "phone"]
    ordering_fields = ["membership_number", "joined_on", "status"]

    @action(detail=False, methods=["get"])
    def lookup(self, request):
        members = self.get_queryset().filter(status=LibraryMember.Status.ACTIVE)
        return Response(self.get_serializer(members, many=True).data)

    @action(detail=False, methods=["get"])
    def people_lookup(self, request):
        from apps.staff.models import Staff
        from apps.students.models import Student
        tenant = self.get_madrasa()
        students = Student.objects.filter(madrasa=tenant, status=Student.Status.ACTIVE).values("id", "full_name", "registration_number")
        staff = Staff.objects.filter(madrasa=tenant, is_active=True).values("id", "full_name", "role")
        return Response({"students": list(students), "staff": list(staff)})


@extend_schema(tags=["Library Circulation"])
class LibraryLoanViewSet(LibraryViewSet):
    queryset = LibraryLoan.objects.select_related("copy__book", "member__student", "member__staff", "issued_by", "returned_by")
    serializer_class = LibraryLoanSerializer
    search_fields = ["copy__book__title", "copy__accession_number", "member__membership_number", "member__student__full_name", "member__staff__full_name", "member__external_name"]
    ordering_fields = ["issued_on", "due_on", "returned_on", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        loan_status = self.request.query_params.get("status")
        member = self.request.query_params.get("member")
        if loan_status:
            queryset = queryset.filter(status=loan_status)
        if member:
            queryset = queryset.filter(member_id=member)
        today = timezone.localdate()
        queryset.filter(status=LibraryLoan.Status.ISSUED, due_on__lt=today).update(status=LibraryLoan.Status.OVERDUE)
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        copy = LibraryBookCopy.objects.select_for_update().get(pk=serializer.validated_data["copy"].pk)
        if copy.status != LibraryBookCopy.Status.AVAILABLE:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"copy": "This copy is no longer available."})
        loan = serializer.save(madrasa=self.get_madrasa(), issued_by=self.request.user)
        copy.status = LibraryBookCopy.Status.ISSUED
        copy.save(update_fields=["status"])
        return loan

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def return_book(self, request, pk=None):
        loan = self.get_object()
        if loan.status not in [LibraryLoan.Status.ISSUED, LibraryLoan.Status.OVERDUE]:
            return Response({"detail": "This loan is not active."}, status=status.HTTP_400_BAD_REQUEST)
        returned_on = request.data.get("returned_on") or timezone.localdate().isoformat()
        try:
            returned_on = date.fromisoformat(str(returned_on))
        except ValueError:
            return Response({"returned_on": ["Invalid return date."]}, status=status.HTTP_400_BAD_REQUEST)
        if returned_on < loan.issued_on:
            return Response({"returned_on": ["Return date cannot precede issue date."]}, status=status.HTTP_400_BAD_REQUEST)
        copy_status = request.data.get("copy_status", LibraryBookCopy.Status.AVAILABLE)
        if copy_status not in [LibraryBookCopy.Status.AVAILABLE, LibraryBookCopy.Status.DAMAGED, LibraryBookCopy.Status.REPAIR]:
            return Response({"copy_status": ["Invalid returned copy status."]}, status=status.HTTP_400_BAD_REQUEST)
        loan.returned_on = returned_on
        loan.status = LibraryLoan.Status.RETURNED
        loan.returned_by = request.user
        loan.save(update_fields=["returned_on", "status", "returned_by"])
        loan.copy.status = copy_status
        loan.copy.condition_notes = request.data.get("condition_notes", loan.copy.condition_notes)
        loan.copy.save(update_fields=["status", "condition_notes"])
        fine_per_day = Decimal(str(request.data.get("fine_per_day", 0) or 0))
        overdue_days = max((returned_on - loan.due_on).days, 0)
        if overdue_days and fine_per_day > 0:
            LibraryFine.objects.update_or_create(madrasa=self.get_madrasa(), loan=loan, defaults={"amount": fine_per_day * overdue_days, "reason": f"{overdue_days} days overdue", "status": LibraryFine.Status.UNPAID})
        return Response(self.get_serializer(loan).data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        loan = self.get_object()
        if loan.status not in [LibraryLoan.Status.ISSUED, LibraryLoan.Status.OVERDUE]:
            return Response({"detail": "Only active loans can be renewed."}, status=status.HTTP_400_BAD_REQUEST)
        if loan.copy.book.reservations.filter(status=LibraryReservation.Status.WAITING).exclude(member=loan.member).exists():
            return Response({"detail": "This book is reserved by another member."}, status=status.HTTP_400_BAD_REQUEST)
        days = int(request.data.get("days", loan.member.loan_days))
        if days < 1 or days > 90:
            return Response({"days": ["Renewal must be between 1 and 90 days."]}, status=status.HTTP_400_BAD_REQUEST)
        loan.due_on = max(loan.due_on, timezone.localdate()) + timedelta(days=days)
        loan.renewal_count += 1
        loan.status = LibraryLoan.Status.ISSUED
        loan.save(update_fields=["due_on", "renewal_count", "status"])
        return Response(self.get_serializer(loan).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def mark_lost(self, request, pk=None):
        loan = self.get_object()
        if loan.status not in [LibraryLoan.Status.ISSUED, LibraryLoan.Status.OVERDUE]:
            return Response({"detail": "Only active loans can be marked lost."}, status=status.HTTP_400_BAD_REQUEST)
        loan.status = LibraryLoan.Status.LOST
        loan.save(update_fields=["status"])
        loan.copy.status = LibraryBookCopy.Status.LOST
        loan.copy.save(update_fields=["status"])
        amount = Decimal(str(request.data.get("amount", loan.copy.purchase_price) or 0))
        if amount > 0:
            LibraryFine.objects.update_or_create(madrasa=self.get_madrasa(), loan=loan, defaults={"amount": amount, "reason": "Lost book replacement", "status": LibraryFine.Status.UNPAID})
        return Response(self.get_serializer(loan).data)


@extend_schema(tags=["Library Circulation"])
class LibraryFineViewSet(LibraryViewSet):
    queryset = LibraryFine.objects.select_related("loan__member", "loan__copy__book")
    serializer_class = LibraryFineSerializer
    search_fields = ["loan__member__membership_number", "loan__copy__book__title", "receipt_number"]
    ordering_fields = ["assessed_on", "amount", "status"]

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        fine = self.get_object()
        if fine.status != LibraryFine.Status.UNPAID:
            return Response({"detail": "Only unpaid fines can be paid."}, status=status.HTTP_400_BAD_REQUEST)
        fine.status = LibraryFine.Status.PAID
        fine.paid_on = timezone.localdate()
        fine.receipt_number = request.data.get("receipt_number", fine.receipt_number)
        fine.save(update_fields=["status", "paid_on", "receipt_number"])
        return Response(self.get_serializer(fine).data)

    @action(detail=True, methods=["post"])
    def waive(self, request, pk=None):
        if not user_has_permission(request.user, "library.manage"):
            return Response({"detail": "You do not have permission to waive fines."}, status=status.HTTP_403_FORBIDDEN)
        fine = self.get_object()
        fine.status = LibraryFine.Status.WAIVED
        fine.paid_on = None
        fine.notes = request.data.get("notes", fine.notes)
        fine.save(update_fields=["status", "paid_on", "notes"])
        return Response(self.get_serializer(fine).data)


@extend_schema(tags=["Library"])
class LibraryReservationViewSet(LibraryViewSet):
    queryset = LibraryReservation.objects.select_related("book", "member__student", "member__staff")
    serializer_class = LibraryReservationSerializer
    search_fields = ["book__title", "member__membership_number", "member__student__full_name", "member__staff__full_name"]
    ordering_fields = ["reserved_on", "expires_on", "status"]


class LibraryDashboardViewSet(TenantScopedViewSetMixin, viewsets.ViewSet):
    queryset = LibraryBook.objects.none()

    def list(self, request):
        tenant = self.get_madrasa()
        today = timezone.localdate()
        LibraryLoan.objects.filter(madrasa=tenant, status=LibraryLoan.Status.ISSUED, due_on__lt=today).update(status=LibraryLoan.Status.OVERDUE)
        copies = LibraryBookCopy.objects.filter(madrasa=tenant)
        loans = LibraryLoan.objects.filter(madrasa=tenant)
        popular = LibraryBook.objects.filter(madrasa=tenant).annotate(issue_count=Count("copies__loans")).order_by("-issue_count", "title")[:5]
        return Response({
            "titles": LibraryBook.objects.filter(madrasa=tenant).count(),
            "copies": copies.count(),
            "available": copies.filter(status=LibraryBookCopy.Status.AVAILABLE).count(),
            "issued": loans.filter(status=LibraryLoan.Status.ISSUED).count(),
            "overdue": loans.filter(status=LibraryLoan.Status.OVERDUE).count(),
            "members": LibraryMember.objects.filter(madrasa=tenant, status=LibraryMember.Status.ACTIVE).count(),
            "unpaid_fines": LibraryFine.objects.filter(madrasa=tenant, status=LibraryFine.Status.UNPAID).aggregate(value=Sum("amount"))["value"] or Decimal("0"),
            "recent_loans": LibraryLoanSerializer(loans.select_related("copy__book", "member__student", "member__staff")[:10], many=True).data,
            "popular_books": [{"id": book.id, "title": book.title, "author": book.author, "issue_count": book.issue_count} for book in popular],
        })
