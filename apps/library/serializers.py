from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import LibraryBook, LibraryBookCopy, LibraryCategory, LibraryFine, LibraryLoan, LibraryMember, LibraryReservation, LibraryShelf


class LibraryCategorySerializer(serializers.ModelSerializer):
    book_count = serializers.IntegerField(source="books.count", read_only=True)

    class Meta:
        model = LibraryCategory
        fields = ["id", "name", "code", "description", "is_active", "book_count"]


class LibraryShelfSerializer(serializers.ModelSerializer):
    copy_count = serializers.IntegerField(source="book_copies.count", read_only=True)

    class Meta:
        model = LibraryShelf
        fields = ["id", "name", "code", "location", "description", "copy_count"]


class LibraryBookCopySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    shelf_name = serializers.CharField(source="shelf.name", read_only=True)

    class Meta:
        model = LibraryBookCopy
        fields = ["id", "book", "book_title", "accession_number", "barcode", "shelf", "shelf_name", "status", "acquisition_date", "acquisition_source", "purchase_price", "condition_notes"]


class LibraryBookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    total_copies = serializers.IntegerField(source="copies.count", read_only=True)
    available_copies = serializers.SerializerMethodField()
    copies = LibraryBookCopySerializer(many=True, read_only=True)

    class Meta:
        model = LibraryBook
        fields = ["id", "category", "category_name", "title", "author", "publisher", "isbn", "language", "edition", "publication_year", "description", "cover", "created_at", "total_copies", "available_copies", "copies"]
        read_only_fields = ["created_at"]

    def get_available_copies(self, book):
        return book.copies.filter(status=LibraryBookCopy.Status.AVAILABLE).count()


class LibraryMemberSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    active_loans = serializers.SerializerMethodField()

    class Meta:
        model = LibraryMember
        fields = ["id", "membership_number", "member_type", "student", "staff", "external_name", "display_name", "phone", "joined_on", "status", "borrowing_limit", "loan_days", "notes", "active_loans"]

    def get_active_loans(self, member):
        return member.loans.filter(status__in=[LibraryLoan.Status.ISSUED, LibraryLoan.Status.OVERDUE]).count()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        member_type = attrs.get("member_type", getattr(self.instance, "member_type", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        staff = attrs.get("staff", getattr(self.instance, "staff", None))
        external_name = attrs.get("external_name", getattr(self.instance, "external_name", ""))
        if member_type != LibraryMember.MemberType.STUDENT:
            attrs["student"] = None
        if member_type != LibraryMember.MemberType.STAFF:
            attrs["staff"] = None
        if member_type != LibraryMember.MemberType.EXTERNAL:
            attrs["external_name"] = ""
        if member_type == LibraryMember.MemberType.STUDENT and not student:
            raise serializers.ValidationError({"student": "Student is required for a student member."})
        if member_type == LibraryMember.MemberType.STAFF and not staff:
            raise serializers.ValidationError({"staff": "Staff is required for a staff member."})
        if member_type == LibraryMember.MemberType.EXTERNAL and not external_name:
            raise serializers.ValidationError({"external_name": "Name is required for an external member."})
        return attrs


class LibraryLoanSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="copy.book.title", read_only=True)
    accession_number = serializers.CharField(source="copy.accession_number", read_only=True)
    member_name = serializers.CharField(source="member.display_name", read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)

    class Meta:
        model = LibraryLoan
        fields = ["id", "copy", "book_title", "accession_number", "member", "member_name", "issued_on", "due_on", "returned_on", "status", "renewal_count", "issued_by", "returned_by", "notes", "days_overdue"]
        read_only_fields = ["status", "returned_on", "renewal_count", "issued_by", "returned_by"]
        extra_kwargs = {"due_on": {"required": False}}

    def validate(self, attrs):
        attrs = super().validate(attrs)
        copy = attrs.get("copy")
        member = attrs.get("member")
        issued_on = attrs.get("issued_on", timezone.localdate())
        if copy and copy.status != LibraryBookCopy.Status.AVAILABLE:
            raise serializers.ValidationError({"copy": "This book copy is not available."})
        if member and member.status != LibraryMember.Status.ACTIVE:
            raise serializers.ValidationError({"member": "This library membership is not active."})
        if member and member.loans.filter(status__in=[LibraryLoan.Status.ISSUED, LibraryLoan.Status.OVERDUE]).count() >= member.borrowing_limit:
            raise serializers.ValidationError({"member": "The member has reached the borrowing limit."})
        if copy and member and copy.madrasa_id != member.madrasa_id:
            raise serializers.ValidationError("Copy and member must belong to the same madrasa.")
            if member:
                attrs["due_on"] = attrs.get("due_on") or issued_on + timedelta(days=member.loan_days)
            elif not attrs.get("due_on"):
                raise serializers.ValidationError({"member": "A member is required."})
        if attrs["due_on"] < issued_on:
            raise serializers.ValidationError({"due_on": "Due date cannot precede issue date."})
        return attrs


class LibraryFineSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="loan.member.display_name", read_only=True)
    book_title = serializers.CharField(source="loan.copy.book.title", read_only=True)

    class Meta:
        model = LibraryFine
        fields = ["id", "loan", "member_name", "book_title", "amount", "reason", "status", "assessed_on", "paid_on", "receipt_number", "notes"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        status = attrs.get("status", getattr(self.instance, "status", None))
        paid_on = attrs.get("paid_on", getattr(self.instance, "paid_on", None))
        if status == LibraryFine.Status.PAID and not paid_on:
            attrs["paid_on"] = timezone.localdate()
        if status != LibraryFine.Status.PAID:
            attrs["paid_on"] = None
        return attrs


class LibraryReservationSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    member_name = serializers.CharField(source="member.display_name", read_only=True)

    class Meta:
        model = LibraryReservation
        fields = ["id", "book", "book_title", "member", "member_name", "reserved_on", "expires_on", "status", "notes"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        member = attrs.get("member", getattr(self.instance, "member", None))
        if member and member.status != LibraryMember.Status.ACTIVE:
            raise serializers.ValidationError({"member": "This library membership is not active."})
        return attrs
