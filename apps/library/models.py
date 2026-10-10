from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class LibraryCategory(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_categories")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name"], name="unique_library_category_per_madrasa")]

    def __str__(self):
        return self.name


class LibraryShelf(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_shelves")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "code"], name="unique_library_shelf_code_per_madrasa")]

    def __str__(self):
        return f"{self.code} — {self.name}"


class LibraryBook(models.Model):
    class Language(models.TextChoices):
        URDU = "urdu", "اردو"
        ARABIC = "arabic", "عربی"
        ENGLISH = "english", "انگریزی"
        PERSIAN = "persian", "فارسی"
        OTHER = "other", "دیگر"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_books")
    category = models.ForeignKey(LibraryCategory, on_delete=models.PROTECT, related_name="books")
    title = models.CharField(max_length=250)
    author = models.CharField(max_length=200, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=30, blank=True)
    language = models.CharField(max_length=20, choices=Language.choices, default=Language.URDU)
    edition = models.CharField(max_length=100, blank=True)
    publication_year = models.PositiveSmallIntegerField(blank=True, null=True)
    description = models.TextField(blank=True)
    cover = models.ImageField(upload_to="library/covers/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "author"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "isbn"], condition=~models.Q(isbn=""), name="unique_book_isbn_per_madrasa")]

    def __str__(self):
        return self.title


class LibraryBookCopy(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "دستیاب"
        ISSUED = "issued", "جاری شدہ"
        LOST = "lost", "گم شدہ"
        DAMAGED = "damaged", "خراب"
        REPAIR = "repair", "مرمت"
        WITHDRAWN = "withdrawn", "خارج شدہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_book_copies")
    book = models.ForeignKey(LibraryBook, on_delete=models.PROTECT, related_name="copies")
    accession_number = models.CharField(max_length=60)
    barcode = models.CharField(max_length=80, blank=True)
    shelf = models.ForeignKey(LibraryShelf, on_delete=models.SET_NULL, blank=True, null=True, related_name="book_copies")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    acquisition_date = models.DateField(blank=True, null=True)
    acquisition_source = models.CharField(max_length=150, blank=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    condition_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["accession_number"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "accession_number"], name="unique_accession_number_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "barcode"], condition=~models.Q(barcode=""), name="unique_library_barcode_per_madrasa"),
        ]

    def __str__(self):
        return f"{self.accession_number} — {self.book.title}"


class LibraryMember(models.Model):
    class MemberType(models.TextChoices):
        STUDENT = "student", "طالب علم"
        STAFF = "staff", "عملہ"
        EXTERNAL = "external", "بیرونی"

    class Status(models.TextChoices):
        ACTIVE = "active", "فعال"
        SUSPENDED = "suspended", "معطل"
        CLOSED = "closed", "بند"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_members")
    membership_number = models.CharField(max_length=50)
    member_type = models.CharField(max_length=20, choices=MemberType.choices)
    student = models.OneToOneField("students.Student", on_delete=models.PROTECT, blank=True, null=True, related_name="library_membership")
    staff = models.OneToOneField("staff.Staff", on_delete=models.PROTECT, blank=True, null=True, related_name="library_membership")
    external_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    joined_on = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    borrowing_limit = models.PositiveSmallIntegerField(default=3)
    loan_days = models.PositiveSmallIntegerField(default=14)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["membership_number"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "membership_number"], name="unique_library_membership_per_madrasa")]

    @property
    def display_name(self):
        if self.student_id:
            return self.student.full_name
        if self.staff_id:
            return self.staff.full_name
        return self.external_name

    def __str__(self):
        return f"{self.membership_number} — {self.display_name}"


class LibraryLoan(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "جاری"
        RETURNED = "returned", "واپس"
        OVERDUE = "overdue", "تاخیر"
        LOST = "lost", "گم شدہ"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_loans")
    copy = models.ForeignKey(LibraryBookCopy, on_delete=models.PROTECT, related_name="loans")
    member = models.ForeignKey(LibraryMember, on_delete=models.PROTECT, related_name="loans")
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField()
    returned_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED, db_index=True)
    renewal_count = models.PositiveSmallIntegerField(default=0)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="library_loans_issued")
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="library_loans_returned")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-issued_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["copy"], condition=models.Q(status__in=["issued", "overdue"]), name="one_active_loan_per_copy")]

    @property
    def days_overdue(self):
        end = self.returned_on or timezone.localdate()
        return max((end - self.due_on).days, 0)


class LibraryFine(models.Model):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "واجب الادا"
        PAID = "paid", "ادا شدہ"
        WAIVED = "waived", "معاف"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_fines")
    loan = models.OneToOneField(LibraryLoan, on_delete=models.PROTECT, related_name="fine")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    reason = models.CharField(max_length=250)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    assessed_on = models.DateField(default=timezone.localdate)
    paid_on = models.DateField(blank=True, null=True)
    receipt_number = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assessed_on", "-id"]


class LibraryReservation(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "منتظر"
        FULFILLED = "fulfilled", "مکمل"
        CANCELLED = "cancelled", "منسوخ"
        EXPIRED = "expired", "میعاد ختم"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="library_reservations")
    book = models.ForeignKey(LibraryBook, on_delete=models.PROTECT, related_name="reservations")
    member = models.ForeignKey(LibraryMember, on_delete=models.PROTECT, related_name="reservations")
    reserved_on = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["reserved_on", "id"]
        constraints = [models.UniqueConstraint(fields=["book", "member"], condition=models.Q(status="waiting"), name="unique_waiting_book_reservation")]
