from django.db import models


class Fund(models.Model):
    madrasa = models.ForeignKey("users.Madrasa", on_delete=models.CASCADE, related_name="funds", null=True, blank=True)
    class FundType(models.TextChoices):
        ZAKAT = "zakat", "Zakat"
        CHANDA = "chanda", "Chanda"
        LILLAH = "lillah", "Lillah"
        FITRANA = "fitrana", "Fitrana"
        OTHER = "other", "Other"

    name = models.CharField(max_length=150, unique=True)
    fund_type = models.CharField(max_length=20, choices=FundType.choices)
    restriction = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

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
    receipt_number = models.CharField(max_length=60, blank=True, null=True, unique=True)

    class Meta:
        ordering = ["-date"]


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

    class Meta:
        ordering = ["-date"]
