from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


money_validators = [MinValueValidator(0)]


class Fund(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="funds", null=True, blank=True)
    class FundType(models.TextChoices):
        ZAKAT = "zakat", "Zakat"
        CHANDA = "chanda", "Chanda"
        LILLAH = "lillah", "Lillah"
        FITRANA = "fitrana", "Fitrana"
        OTHER = "other", "Other"

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, blank=True)
    fund_type = models.CharField(max_length=20, choices=FundType.choices)
    restriction = models.TextField(blank=True)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=money_validators)
    is_restricted = models.BooleanField(default=False)
    allow_overdraft = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["madrasa", "name"], name="unique_fund_name_per_madrasa"),
            models.UniqueConstraint(fields=["madrasa", "code"], condition=~models.Q(code=""), name="unique_fund_code_per_madrasa"),
        ]

    def __str__(self):
        return self.name


class Donor(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="donors", null=True, blank=True)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Donation(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="donations", null=True, blank=True)
    donor = models.ForeignKey(Donor, on_delete=models.PROTECT, related_name="donations")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="donations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    receipt_number = models.CharField(max_length=60, blank=True, null=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "receipt_number"], condition=models.Q(receipt_number__isnull=False), name="unique_donation_receipt_per_madrasa")]


class StudentFeeLog(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_fee_logs", null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="fee_logs")
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ["-due_date"]


class StudentMonthlyFee(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_monthly_fees", null=True, blank=True)
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="monthly_fees")
    month = models.DateField(help_text="First day of the billed month.")
    tuition_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hostel_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    previous_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()

    class Meta:
        ordering = ["-month", "student__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["student", "month"], name="unique_student_monthly_fee")
        ]

    @property
    def current_charges(self):
        return max(self.tuition_fee + self.hostel_fee - self.discount, 0)

    @property
    def total_due(self):
        return self.previous_balance + self.current_charges

    @property
    def amount_paid(self):
        return sum(payment.amount for payment in self.payments.all())

    @property
    def outstanding_balance(self):
        return max(self.total_due - self.amount_paid, 0)


class StudentFeePayment(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_fee_payments", null=True, blank=True)
    monthly_fee = models.ForeignKey(StudentMonthlyFee, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    receipt_number = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]


class TeacherSalary(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="teacher_salaries", null=True, blank=True)
    teacher = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="salary_records")
    month = models.DateField(help_text="Use the first day of the salary month.")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    basic_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    payment_method = models.CharField(max_length=20, choices=[("cash", "Cash"), ("bank", "Bank"), ("mobile", "Mobile wallet"), ("cheque", "Cheque")], default="cash")
    payment_reference = models.CharField(max_length=100, blank=True)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, blank=True, null=True, related_name="salary_records")

    class Meta:
        ordering = ["-month", "teacher__full_name"]
        constraints = [
            models.UniqueConstraint(fields=["teacher", "month"], name="unique_teacher_salary_per_month")
        ]


class StudentSponsorship(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="student_sponsorships", null=True, blank=True)
    donor = models.ForeignKey(Donor, on_delete=models.PROTECT, related_name="sponsorships")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="sponsorships")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="sponsorships")
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ["-start_date"]


class Expense(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="expenses", null=True, blank=True)
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="expenses")
    category = models.ForeignKey("FinancialCategory", on_delete=models.PROTECT, blank=True, null=True, related_name="expenses")
    payee = models.CharField(max_length=200, blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]


class FinancialCategory(models.Model):
    class CategoryType(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="financial_categories")
    name = models.CharField(max_length=150)
    category_type = models.CharField(max_length=20, choices=CategoryType.choices)
    code = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category_type", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "category_type", "name"], name="unique_finance_category_per_madrasa")]


class FundTransfer(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="fund_transfers")
    source_fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="outgoing_transfers")
    destination_fund = models.ForeignKey(Fund, on_delete=models.PROTECT, related_name="incoming_transfers")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    date = models.DateField(default=timezone.localdate)
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="fund_transfers_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.CheckConstraint(check=~models.Q(source_fund=models.F("destination_fund")), name="different_transfer_funds")]


class Budget(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        CLOSED = "closed", "Closed"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="budgets")
    name = models.CharField(max_length=200)
    fiscal_year = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="budgets_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="budgets_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fiscal_year", "name"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "name", "fiscal_year"], name="unique_budget_name_year_per_madrasa")]


class BudgetLine(models.Model):
    class LineType(models.TextChoices):
        INCOME = "income", "Income"
        EXPENSE = "expense", "Expense"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="budget_lines")
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="lines")
    line_type = models.CharField(max_length=20, choices=LineType.choices)
    category = models.ForeignKey(FinancialCategory, on_delete=models.PROTECT, blank=True, null=True, related_name="budget_lines")
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, blank=True, null=True, related_name="budget_lines")
    title = models.CharField(max_length=200)
    planned_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["line_type", "title"]


class StaffCompensation(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="staff_compensations")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="compensation_records")
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0.01)])
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    fixed_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, blank=True, null=True, related_name="staff_compensations")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["staff__full_name", "-effective_from"]
        constraints = [models.UniqueConstraint(fields=["staff", "effective_from"], name="unique_staff_compensation_start")]


class PayrollRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="payroll_runs")
    month = models.DateField(help_text="First day of the payroll month.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="payroll_runs_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="payroll_runs_approved")
    approved_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month"]
        constraints = [models.UniqueConstraint(fields=["madrasa", "month"], name="unique_payroll_month_per_madrasa")]


class PayrollItem(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="payroll_items")
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="items")
    staff = models.ForeignKey("staff.Staff", on_delete=models.PROTECT, related_name="payroll_items")
    basic_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=money_validators)
    fund = models.ForeignKey(Fund, on_delete=models.PROTECT, blank=True, null=True, related_name="payroll_items")
    payment_method = models.CharField(max_length=20, choices=[("cash", "Cash"), ("bank", "Bank"), ("mobile", "Mobile wallet"), ("cheque", "Cheque")], default="cash")
    payment_reference = models.CharField(max_length=100, blank=True)
    paid_on = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["staff__full_name"]
        constraints = [models.UniqueConstraint(fields=["payroll_run", "staff"], name="unique_staff_per_payroll_run")]
