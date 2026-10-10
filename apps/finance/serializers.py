from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Budget, BudgetLine, Donation, Donor, Expense, FinancialCategory, Fund, FundTransfer, PayrollItem, PayrollRun, StaffCompensation, StudentFeeLog, StudentFeePayment, StudentMonthlyFee, StudentSponsorship, TeacherSalary


class PositiveAmountMixin:
    amount_fields = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field in self.amount_fields:
            if field in attrs and attrs[field] is not None and attrs[field] < 0:
                raise serializers.ValidationError({field: "Amount cannot be negative."})
        return attrs


class FundSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    income = serializers.SerializerMethodField()
    expenses = serializers.SerializerMethodField()

    def _totals(self, fund):
        from django.db.models import Sum
        donations = fund.donations.aggregate(value=Sum("amount"))["value"] or Decimal("0")
        incoming = fund.incoming_transfers.aggregate(value=Sum("amount"))["value"] or Decimal("0")
        expenses = fund.expenses.aggregate(value=Sum("amount"))["value"] or Decimal("0")
        salaries = fund.salary_records.filter(is_paid=True).aggregate(value=Sum("amount"))["value"] or Decimal("0")
        payroll = fund.payroll_items.filter(payroll_run__status=PayrollRun.Status.PAID).aggregate(value=Sum("net_amount"))["value"] or Decimal("0")
        outgoing = fund.outgoing_transfers.aggregate(value=Sum("amount"))["value"] or Decimal("0")
        return donations + incoming, expenses + salaries + payroll + outgoing

    def get_income(self, fund):
        return self._totals(fund)[0]

    def get_expenses(self, fund):
        return self._totals(fund)[1]

    def get_balance(self, fund):
        income, expenses = self._totals(fund)
        return fund.opening_balance + income - expenses

    class Meta:
        model = Fund
        fields = ["id", "name", "code", "fund_type", "restriction", "opening_balance", "is_restricted", "allow_overdraft", "is_active", "income", "expenses", "balance"]


class DonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donor
        fields = ["id", "full_name", "phone", "address"]


class DonationSerializer(PositiveAmountMixin, serializers.ModelSerializer):
    amount_fields = ("amount",)
    donor_name = serializers.CharField(source="donor.full_name", read_only=True)
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = Donation
        fields = ["id", "donor", "donor_name", "fund", "fund_name", "amount", "date", "receipt_number"]

    def validate_receipt_number(self, value):
        return value.strip() or None if value else None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class StudentFeeLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = StudentFeeLog
        fields = ["id", "student", "student_name", "amount_due", "due_date", "is_paid"]


class StudentFeePaymentSerializer(PositiveAmountMixin, serializers.ModelSerializer):
    amount_fields = ("amount",)
    student = serializers.IntegerField(source="monthly_fee.student_id", read_only=True)
    student_name = serializers.CharField(source="monthly_fee.student.full_name", read_only=True)
    registration_number = serializers.CharField(source="monthly_fee.student.registration_number", read_only=True)
    academic_class_name = serializers.CharField(source="monthly_fee.student.current_class.name", read_only=True)
    billing_month = serializers.DateField(source="monthly_fee.month", read_only=True)

    class Meta:
        model = StudentFeePayment
        fields = ["id", "monthly_fee", "student", "student_name", "registration_number", "academic_class_name", "billing_month", "amount", "payment_date", "receipt_number", "notes"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class StudentMonthlyFeeSerializer(PositiveAmountMixin, serializers.ModelSerializer):
    amount_fields = ("tuition_fee", "hostel_fee", "discount", "previous_balance")
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    registration_number = serializers.CharField(source="student.registration_number", read_only=True)
    class_name = serializers.CharField(source="student.current_class.name", read_only=True)
    current_charges = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payments = StudentFeePaymentSerializer(many=True, read_only=True)

    class Meta:
        model = StudentMonthlyFee
        fields = ["id", "student", "student_name", "registration_number", "class_name", "month", "tuition_fee", "hostel_fee", "discount", "previous_balance", "current_charges", "total_due", "amount_paid", "outstanding_balance", "due_date", "payments"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tuition = attrs.get("tuition_fee", getattr(self.instance, "tuition_fee", 0))
        hostel = attrs.get("hostel_fee", getattr(self.instance, "hostel_fee", 0))
        discount = attrs.get("discount", getattr(self.instance, "discount", 0))
        if discount > tuition + hostel:
            raise serializers.ValidationError({"discount": "Discount cannot exceed current charges."})
        return attrs


class TeacherSalarySerializer(PositiveAmountMixin, serializers.ModelSerializer):
    amount_fields = ("amount", "basic_amount", "allowances", "deductions")
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)

    class Meta:
        model = TeacherSalary
        fields = ["id", "teacher", "teacher_name", "month", "amount", "basic_amount", "allowances", "deductions", "fund", "payment_method", "payment_reference", "payment_date", "is_paid", "notes"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        month = attrs.get("month", getattr(self.instance, "month", None))
        if month and month.day != 1:
            raise serializers.ValidationError({"month": "Salary month must be the first day of a month."})
        paid = attrs.get("is_paid", getattr(self.instance, "is_paid", False))
        payment_date = attrs.get("payment_date", getattr(self.instance, "payment_date", None))
        if paid and not payment_date:
            attrs["payment_date"] = timezone.localdate()
        if not paid:
            attrs["payment_date"] = None
        basic = attrs.get("basic_amount", getattr(self.instance, "basic_amount", 0))
        allowances = attrs.get("allowances", getattr(self.instance, "allowances", 0))
        deductions = attrs.get("deductions", getattr(self.instance, "deductions", 0))
        if basic or allowances or deductions:
            if deductions > basic + allowances:
                raise serializers.ValidationError({"deductions": "Deductions cannot exceed gross salary."})
            attrs["amount"] = basic + allowances - deductions
        return attrs

    def validate_amount(self, value):
        if value <= 0 and not any(Decimal(str(self.initial_data.get(field, 0) or 0)) > 0 for field in ("basic_amount", "allowances")):
            raise serializers.ValidationError("Salary must be greater than zero.")
        return value


class StudentSponsorshipSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.full_name", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = StudentSponsorship
        fields = ["id", "donor", "donor_name", "student", "student_name", "fund", "fund_name", "start_date", "end_date"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("end_date") and attrs["end_date"] < attrs.get("start_date", getattr(self.instance, "start_date", attrs["end_date"])):
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        return attrs


class ExpenseSerializer(PositiveAmountMixin, serializers.ModelSerializer):
    amount_fields = ("amount",)
    fund_name = serializers.CharField(source="fund.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Expense
        fields = ["id", "title", "amount", "date", "fund", "fund_name", "category", "category_name", "payee", "reference_number", "notes"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class FinancialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialCategory
        fields = ["id", "name", "category_type", "code", "is_active"]


class FundTransferSerializer(serializers.ModelSerializer):
    source_fund_name = serializers.CharField(source="source_fund.name", read_only=True)
    destination_fund_name = serializers.CharField(source="destination_fund.name", read_only=True)

    class Meta:
        model = FundTransfer
        fields = ["id", "source_fund", "source_fund_name", "destination_fund", "destination_fund_name", "amount", "date", "reference_number", "notes", "created_by", "created_at"]
        read_only_fields = ["created_by", "created_at"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        source = attrs.get("source_fund")
        destination = attrs.get("destination_fund")
        if source == destination:
            raise serializers.ValidationError({"destination_fund": "Source and destination funds must differ."})
        amount = attrs.get("amount", Decimal("0"))
        if source and not source.allow_overdraft:
            balance = Decimal(str(FundSerializer(context=self.context).get_balance(source)))
            if amount > balance:
                raise serializers.ValidationError({"amount": "Transfer exceeds the available fund balance."})
        return attrs


class BudgetLineSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = BudgetLine
        fields = ["id", "line_type", "category", "category_name", "fund", "fund_name", "title", "planned_amount", "notes"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        category = attrs.get("category", getattr(self.instance, "category", None))
        line_type = attrs.get("line_type", getattr(self.instance, "line_type", None))
        if category and category.category_type != line_type:
            raise serializers.ValidationError({"category": "Category type must match the budget line type."})
        return attrs


class BudgetSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, required=False)
    planned_income = serializers.SerializerMethodField()
    planned_expenses = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = ["id", "name", "fiscal_year", "status", "notes", "lines", "planned_income", "planned_expenses", "created_by", "approved_by", "approved_at", "created_at"]
        read_only_fields = ["created_by", "approved_by", "approved_at", "created_at"]

    def get_planned_income(self, budget):
        return sum(line.planned_amount for line in budget.lines.all() if line.line_type == BudgetLine.LineType.INCOME)

    def get_planned_expenses(self, budget):
        return sum(line.planned_amount for line in budget.lines.all() if line.line_type == BudgetLine.LineType.EXPENSE)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("status") in [Budget.Status.APPROVED, Budget.Status.CLOSED]:
            raise serializers.ValidationError({"status": "Use budget workflow actions for this status."})
        tenant = self.context["request"].user.profile.madrasa
        line_keys = set()
        for line in attrs.get("lines", []):
            for related in [line.get("category"), line.get("fund")]:
                if related and related.madrasa_id != tenant.id:
                    raise serializers.ValidationError({"lines": "Budget relations must belong to the active madrasa."})
            if line.get("category") and line["category"].category_type != line["line_type"]:
                raise serializers.ValidationError({"lines": "Category type must match the budget line type."})
            key = (line["line_type"], line.get("category"), line.get("fund"), line["title"].strip().lower())
            if key in line_keys:
                raise serializers.ValidationError({"lines": "Duplicate budget lines are not allowed."})
            line_keys.add(key)
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop("lines", [])
        budget = super().create(validated_data)
        for line in lines:
            BudgetLine.objects.create(budget=budget, madrasa=budget.madrasa, **line)
        return budget

    def update(self, instance, validated_data):
        if instance.status in [Budget.Status.APPROVED, Budget.Status.CLOSED]:
            raise serializers.ValidationError("Approved budgets are locked.")
        lines = validated_data.pop("lines", None)
        budget = super().update(instance, validated_data)
        if lines is not None:
            budget.lines.all().delete()
            for line in lines:
                BudgetLine.objects.create(budget=budget, madrasa=budget.madrasa, **line)
        return budget


class StaffCompensationSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    gross_salary = serializers.SerializerMethodField()
    net_salary = serializers.SerializerMethodField()

    class Meta:
        model = StaffCompensation
        fields = ["id", "staff", "staff_name", "basic_salary", "allowances", "fixed_deductions", "gross_salary", "net_salary", "effective_from", "effective_to", "fund", "is_active", "notes"]

    def get_gross_salary(self, item):
        return item.basic_salary + item.allowances

    def get_net_salary(self, item):
        return max(item.basic_salary + item.allowances - item.fixed_deductions, Decimal("0"))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        basic = attrs.get("basic_salary", getattr(self.instance, "basic_salary", 0))
        allowances = attrs.get("allowances", getattr(self.instance, "allowances", 0))
        deductions = attrs.get("fixed_deductions", getattr(self.instance, "fixed_deductions", 0))
        if deductions > basic + allowances:
            raise serializers.ValidationError({"fixed_deductions": "Deductions cannot exceed gross salary."})
        if attrs.get("effective_to") and attrs["effective_to"] < attrs.get("effective_from", getattr(self.instance, "effective_from", attrs["effective_to"])):
            raise serializers.ValidationError({"effective_to": "End date cannot precede start date."})
        return attrs


class PayrollItemSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)

    class Meta:
        model = PayrollItem
        fields = ["id", "staff", "staff_name", "basic_amount", "allowances", "deductions", "net_amount", "fund", "payment_method", "payment_reference", "paid_on", "notes"]
        read_only_fields = ["net_amount", "paid_on"]


class PayrollRunSerializer(serializers.ModelSerializer):
    items = PayrollItemSerializer(many=True, read_only=True)
    staff_count = serializers.IntegerField(source="items.count", read_only=True)
    total_gross = serializers.SerializerMethodField()
    total_deductions = serializers.SerializerMethodField()
    total_net = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = ["id", "month", "status", "notes", "staff_count", "total_gross", "total_deductions", "total_net", "items", "created_by", "approved_by", "approved_at", "paid_at", "created_at"]
        read_only_fields = ["created_by", "approved_by", "approved_at", "paid_at", "created_at"]

    def get_total_gross(self, run):
        return sum(item.basic_amount + item.allowances for item in run.items.all())

    def get_total_deductions(self, run):
        return sum(item.deductions for item in run.items.all())

    def get_total_net(self, run):
        return sum(item.net_amount for item in run.items.all())

    def validate_status(self, value):
        if value != PayrollRun.Status.DRAFT:
            raise serializers.ValidationError("Use payroll workflow actions for status changes.")
        return value
