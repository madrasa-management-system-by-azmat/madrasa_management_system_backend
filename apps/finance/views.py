from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.users.rbac import user_has_permission
from rest_framework.views import APIView

from .models import Budget, BudgetLine, Donation, Donor, Expense, FinancialCategory, Fund, FundTransfer, PayrollItem, PayrollRun, StaffCompensation, StudentFeeLog, StudentFeePayment, StudentMonthlyFee, StudentSponsorship, TeacherSalary
from .serializers import BudgetSerializer, DonationSerializer, DonorSerializer, ExpenseSerializer, FinancialCategorySerializer, FundSerializer, FundTransferSerializer, PayrollRunSerializer, StaffCompensationSerializer, StudentFeeLogSerializer, StudentFeePaymentSerializer, StudentMonthlyFeeSerializer, StudentSponsorshipSerializer, TeacherSalarySerializer
from apps.users.permissions import HasTenantRole
from apps.users.tenancy import TenantScopedViewSetMixin, current_madrasa


class FinanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa())


class FinanceLedgerAPIView(APIView):
    permission_classes = [HasTenantRole]

    def get(self, request):
        tenant = current_madrasa(request)
        entries = []
        for payment in StudentFeePayment.objects.filter(madrasa=tenant).select_related("monthly_fee__student"):
            entries.append({"id": f"fee-{payment.id}", "type": "student_fee", "direction": "income", "title": f"طالب علم فیس — {payment.monthly_fee.student.full_name}", "amount": payment.amount, "date": payment.payment_date, "reference": payment.receipt_number, "notes": payment.notes})
        for donation in Donation.objects.filter(madrasa=tenant).select_related("donor", "fund"):
            entries.append({"id": f"donation-{donation.id}", "type": "donation", "direction": "income", "title": f"عطیہ — {donation.donor.full_name}", "amount": donation.amount, "date": donation.date, "reference": donation.receipt_number, "notes": donation.fund.name})
        for expense in Expense.objects.filter(madrasa=tenant).select_related("fund"):
            entries.append({"id": f"expense-{expense.id}", "type": "expense", "direction": "expense", "title": expense.title, "amount": expense.amount, "date": expense.date, "reference": "", "notes": expense.fund.name})
        for salary in TeacherSalary.objects.filter(madrasa=tenant, is_paid=True, payment_date__isnull=False).select_related("teacher"):
            entries.append({"id": f"salary-{salary.id}", "type": "teacher_salary", "direction": "expense", "title": f"استاد تنخواہ — {salary.teacher.full_name}", "amount": salary.amount, "date": salary.payment_date, "reference": str(salary.month), "notes": salary.notes})
        for item in PayrollItem.objects.filter(madrasa=tenant, payroll_run__status=PayrollRun.Status.PAID, paid_on__isnull=False).select_related("staff", "payroll_run"):
            entries.append({"id": f"payroll-{item.id}", "type": "payroll", "direction": "expense", "title": f"عملہ تنخواہ — {item.staff.full_name}", "amount": item.net_amount, "date": item.paid_on, "reference": item.payment_reference or str(item.payroll_run.month), "notes": item.notes})
        entries.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
        income = sum(item["amount"] for item in entries if item["direction"] == "income")
        expenses = sum(item["amount"] for item in entries if item["direction"] == "expense")
        return Response({"income": income, "expenses": expenses, "balance": income - expenses, "entries": entries})

class FinanceYearlyReportAPIView(APIView):
    permission_classes = [HasTenantRole]

    def get(self, request):
        try:
            year = int(request.query_params.get("year", date.today().year))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year."}, status=status.HTTP_400_BAD_REQUEST)

        tenant = current_madrasa(request)
        months = [{"month": month, "income": Decimal("0"), "expenses": Decimal("0")} for month in range(1, 13)]
        for payment in StudentFeePayment.objects.filter(madrasa=tenant, payment_date__year=year):
            months[payment.payment_date.month - 1]["income"] += payment.amount
        for donation in Donation.objects.filter(madrasa=tenant, date__year=year):
            months[donation.date.month - 1]["income"] += donation.amount
        for expense in Expense.objects.filter(madrasa=tenant, date__year=year):
            months[expense.date.month - 1]["expenses"] += expense.amount
        for salary in TeacherSalary.objects.filter(madrasa=tenant, is_paid=True, payment_date__year=year):
            months[salary.payment_date.month - 1]["expenses"] += salary.amount
        for item in PayrollItem.objects.filter(madrasa=tenant, payroll_run__status=PayrollRun.Status.PAID, paid_on__year=year):
            months[item.paid_on.month - 1]["expenses"] += item.net_amount

        running_balance = Decimal("0")
        for item in months:
            item["remaining"] = item["income"] - item["expenses"]
            running_balance += item["remaining"]
            item["running_balance"] = running_balance
        return Response({"year": year, "months": months, "income": sum(item["income"] for item in months), "expenses": sum(item["expenses"] for item in months), "remaining": running_balance})


@extend_schema(tags=["Finance"])
class FundViewSet(FinanceViewSet):
    queryset = Fund.objects.all()
    serializer_class = FundSerializer
    search_fields = ["name", "fund_type"]
    ordering_fields = ["name", "fund_type"]

    @action(detail=False, methods=["get"])
    def statement(self, request):
        fund_id = request.query_params.get("fund")
        funds = self.get_queryset().filter(pk=fund_id) if fund_id else self.get_queryset()
        return Response(FundSerializer(funds, many=True, context={"request": request}).data)


@extend_schema(tags=["Finance"])
class DonorViewSet(FinanceViewSet):
    queryset = Donor.objects.all()
    serializer_class = DonorSerializer
    search_fields = ["full_name", "phone"]
    ordering_fields = ["full_name"]


@extend_schema(tags=["Finance"])
class DonationViewSet(FinanceViewSet):
    queryset = Donation.objects.select_related("donor", "fund")
    serializer_class = DonationSerializer
    search_fields = ["donor__full_name", "fund__name", "receipt_number"]
    ordering_fields = ["date", "amount"]


@extend_schema(tags=["Finance"])
class StudentFeeLogViewSet(FinanceViewSet):
    queryset = StudentFeeLog.objects.select_related("student")
    serializer_class = StudentFeeLogSerializer
    search_fields = ["student__full_name"]
    ordering_fields = ["due_date", "amount_due", "is_paid"]


@extend_schema(tags=["Finance"])
class StudentMonthlyFeeViewSet(FinanceViewSet):
    queryset = StudentMonthlyFee.objects.select_related("student__current_class").prefetch_related("payments")
    serializer_class = StudentMonthlyFeeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["student__full_name", "student__registration_number"]
    ordering_fields = ["month", "due_date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        month = self.request.query_params.get("month")
        academic_class = self.request.query_params.get("academic_class")
        if month:
            queryset = queryset.filter(month=month)
        if academic_class:
            queryset = queryset.filter(student__current_class_id=academic_class)
        return queryset

    @action(detail=False, methods=["post"])
    def generate(self, request):
        tenant = self.get_madrasa()
        month_value = request.data.get("month")
        due_date = request.data.get("due_date")
        academic_class = request.data.get("academic_class")
        student_id = request.data.get("student")
        if not month_value or not due_date or (not academic_class and not student_id):
            return Response({"detail": "month, due_date, and either academic_class or student are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            year, month = map(int, month_value.split("-")[:2])
            billing_month = date(year, month, 1)
            due = date.fromisoformat(due_date)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid month or due_date."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.students.models import Student
        invoices = request.data.get("invoices")
        if invoices is None:
            preview = []
            students = Student.objects.filter(madrasa=tenant, status="active").select_related("current_class")
            students = students.filter(pk=student_id) if student_id else students.filter(current_class_id=academic_class)
            for student in students:
                if not student.current_class_id:
                    return Response({"detail": "The selected student does not have a current class."}, status=status.HTTP_400_BAD_REQUEST)
                if student_id and StudentMonthlyFee.objects.filter(
                    madrasa=tenant, student=student, month=billing_month
                ).exists():
                    return Response(
                        {"detail": "A fee voucher already exists for this student and month."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                preview.append({
                    "student": student.id,
                    "student_name": student.full_name,
                    "registration_number": student.registration_number,
                    "class_name": student.current_class.name,
                    "tuition_fee": student.current_class.tuition_fee,
                    "hostel_fee": student.current_class.hostel_fee if student.residential_status == "resident" else Decimal("0"),
                    "previous_balance": self._previous_balance(student, billing_month),
                    "discount": Decimal("0"),
                    "due_date": due,
                })
            return Response({"month": billing_month, "invoices": preview})

        created = 0
        for invoice in invoices:
            student_id = invoice.get("student")
            if not student_id:
                continue
            student_query = Student.objects.filter(madrasa=tenant, pk=student_id, status="active")
            if academic_class:
                student_query = student_query.filter(current_class_id=academic_class)
            student = student_query.first()
            if not student:
                return Response({"detail": "Invalid student for this madrasa or class."}, status=status.HTTP_400_BAD_REQUEST)
            fee, was_created = StudentMonthlyFee.objects.get_or_create(
                madrasa=tenant,
                student=student,
                month=billing_month,
                defaults={
                    "tuition_fee": invoice.get("tuition_fee", 0),
                    "hostel_fee": invoice.get("hostel_fee", 0),
                    "previous_balance": invoice.get("previous_balance", 0),
                    "discount": invoice.get("discount", 0),
                    "due_date": invoice.get("due_date", due),
                },
            )
            if was_created:
                created += 1
        return Response(
            {
                "created": created,
                "month": billing_month,
                "invoices": StudentMonthlyFeeSerializer(
                    StudentMonthlyFee.objects.filter(
                        madrasa=tenant,
                        month=billing_month,
                        student_id__in=[invoice.get("student") for invoice in invoices if invoice.get("student")],
                    ).select_related("student__current_class").prefetch_related("payments"),
                    many=True,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        fee = self.get_object()
        serializer = StudentFeePaymentSerializer(data={**request.data, "monthly_fee": fee.id})
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data["amount"]
        if amount <= 0 or amount > fee.outstanding_balance:
            return Response({"amount": ["Payment must be greater than zero and not exceed the outstanding balance."]}, status=status.HTTP_400_BAD_REQUEST)
        payment = serializer.save(madrasa=self.get_madrasa())
        return Response(StudentFeePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _previous_balance(student, billing_month):
        previous_fee = StudentMonthlyFee.objects.filter(madrasa=student.madrasa, student=student, month__lt=billing_month).prefetch_related("payments").order_by("-month").first()
        return previous_fee.outstanding_balance if previous_fee else Decimal("0")


@extend_schema(tags=["Finance"])
class StudentFeePaymentViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StudentFeePayment.objects.select_related("monthly_fee__student__current_class")
    serializer_class = StudentFeePaymentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["monthly_fee__student__full_name", "monthly_fee__student__registration_number", "receipt_number"]
    ordering_fields = ["payment_date", "amount"]

    def get_queryset(self):
        queryset = super().get_queryset()
        month = self.request.query_params.get("month")
        academic_class = self.request.query_params.get("academic_class")
        student = self.request.query_params.get("student")
        if month:
            queryset = queryset.filter(monthly_fee__month=month)
        if academic_class:
            queryset = queryset.filter(monthly_fee__student__current_class_id=academic_class)
        if student:
            queryset = queryset.filter(monthly_fee__student_id=student)
        return queryset


@extend_schema(tags=["Finance"])
class TeacherSalaryViewSet(FinanceViewSet):
    queryset = TeacherSalary.objects.select_related("teacher")
    serializer_class = TeacherSalarySerializer
    search_fields = ["teacher__full_name"]
    ordering_fields = ["month", "amount", "is_paid"]


@extend_schema(tags=["Finance"])
class StudentSponsorshipViewSet(FinanceViewSet):
    queryset = StudentSponsorship.objects.select_related("donor", "student", "fund")
    serializer_class = StudentSponsorshipSerializer
    search_fields = ["donor__full_name", "student__full_name", "fund__name"]
    ordering_fields = ["start_date", "end_date"]


@extend_schema(tags=["Finance"])
class ExpenseViewSet(FinanceViewSet):
    queryset = Expense.objects.select_related("fund", "category")
    serializer_class = ExpenseSerializer
    search_fields = ["title", "fund__name"]
    ordering_fields = ["date", "amount", "title"]


@extend_schema(tags=["Finance Control"])
class FinancialCategoryViewSet(FinanceViewSet):
    queryset = FinancialCategory.objects.all()
    serializer_class = FinancialCategorySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name", "category_type"]


@extend_schema(tags=["Finance Control"])
class FundTransferViewSet(FinanceViewSet):
    queryset = FundTransfer.objects.select_related("source_fund", "destination_fund", "created_by")
    serializer_class = FundTransferSerializer
    search_fields = ["source_fund__name", "destination_fund__name", "reference_number"]
    ordering_fields = ["date", "amount"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status in [Budget.Status.APPROVED, Budget.Status.CLOSED]:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Approved budgets are locked.")
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save()


@extend_schema(tags=["Budgeting"])
class BudgetViewSet(FinanceViewSet):
    queryset = Budget.objects.prefetch_related("lines__category", "lines__fund")
    serializer_class = BudgetSerializer
    search_fields = ["name", "fiscal_year"]
    ordering_fields = ["fiscal_year", "name", "status"]

    def perform_create(self, serializer):
        self._validate_tenant_relations(serializer.validated_data, self.get_madrasa())
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    def perform_destroy(self, instance):
        if instance.status != Budget.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft budgets can be deleted.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        budget = self.get_object()
        if budget.status != Budget.Status.DRAFT or not budget.lines.exists():
            return Response({"detail": "Only a populated draft budget can be submitted."}, status=status.HTTP_400_BAD_REQUEST)
        budget.status = Budget.Status.SUBMITTED
        budget.save(update_fields=["status"])
        return Response(self.get_serializer(budget).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not user_has_permission(request.user, "finance.approve"):
            return Response({"detail": "You do not have permission to approve budgets."}, status=status.HTTP_403_FORBIDDEN)
        budget = self.get_object()
        if budget.status != Budget.Status.SUBMITTED:
            return Response({"detail": "Submit the budget before approval."}, status=status.HTTP_400_BAD_REQUEST)
        budget.status = Budget.Status.APPROVED
        budget.approved_by = request.user
        budget.approved_at = timezone.now()
        budget.save(update_fields=["status", "approved_by", "approved_at"])
        return Response(self.get_serializer(budget).data)

    @action(detail=True, methods=["get"])
    def variance(self, request, pk=None):
        budget = self.get_object()
        rows = []
        for line in budget.lines.select_related("category", "fund"):
            if line.line_type == BudgetLine.LineType.INCOME:
                actual = Donation.objects.filter(madrasa=self.get_madrasa(), date__year=budget.fiscal_year)
                if line.fund_id:
                    actual = actual.filter(fund=line.fund)
                actual = actual.aggregate(value=Sum("amount"))["value"] or Decimal("0")
            else:
                actual_query = Expense.objects.filter(madrasa=self.get_madrasa(), date__year=budget.fiscal_year)
                if line.fund_id:
                    actual_query = actual_query.filter(fund=line.fund)
                if line.category_id:
                    actual_query = actual_query.filter(category=line.category)
                actual = actual_query.aggregate(value=Sum("amount"))["value"] or Decimal("0")
            variance = line.planned_amount - actual
            rows.append({"id": line.id, "title": line.title, "line_type": line.line_type, "category": line.category.name if line.category else "", "fund": line.fund.name if line.fund else "", "planned_amount": line.planned_amount, "actual_amount": actual, "variance": variance, "utilization_percentage": round(float(actual / line.planned_amount * 100), 2) if line.planned_amount else 0})
        planned = sum(line.planned_amount for line in budget.lines.all())
        actual = sum(Decimal(str(row["actual_amount"])) for row in rows)
        return Response({"budget": self.get_serializer(budget).data, "lines": rows, "planned": planned, "actual": actual, "variance": planned - actual})


@extend_schema(tags=["Payroll"])
class StaffCompensationViewSet(FinanceViewSet):
    queryset = StaffCompensation.objects.select_related("staff", "fund")
    serializer_class = StaffCompensationSerializer
    search_fields = ["staff__full_name"]
    ordering_fields = ["effective_from", "basic_salary"]

    @action(detail=False, methods=["get"])
    def staff_lookup(self, request):
        from apps.staff.models import Staff
        rows = Staff.objects.filter(madrasa=self.get_madrasa(), is_active=True).values("id", "full_name", "role")
        return Response(list(rows))


@extend_schema(tags=["Payroll"])
class PayrollRunViewSet(FinanceViewSet):
    queryset = PayrollRun.objects.prefetch_related("items__staff", "items__fund")
    serializer_class = PayrollRunSerializer
    search_fields = ["month", "status"]
    ordering_fields = ["month", "status"]

    def perform_create(self, serializer):
        month = serializer.validated_data["month"]
        if month.day != 1:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"month": "Payroll month must be the first day of a month."})
        serializer.save(madrasa=self.get_madrasa(), created_by=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.status != PayrollRun.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Approved or paid payroll is locked.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.status != PayrollRun.Status.DRAFT:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft payroll can be deleted.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def generate(self, request, pk=None):
        run = self.get_object()
        if run.status != PayrollRun.Status.DRAFT:
            return Response({"detail": "Only draft payroll can be regenerated."}, status=status.HTTP_400_BAD_REQUEST)
        compensations = StaffCompensation.objects.filter(
            madrasa=self.get_madrasa(), is_active=True, staff__is_active=True,
            effective_from__lte=run.month,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=run.month)).select_related("staff", "fund")
        run.items.all().delete()
        for compensation in compensations:
            net = max(compensation.basic_salary + compensation.allowances - compensation.fixed_deductions, Decimal("0"))
            PayrollItem.objects.create(madrasa=self.get_madrasa(), payroll_run=run, staff=compensation.staff, basic_amount=compensation.basic_salary, allowances=compensation.allowances, deductions=compensation.fixed_deductions, net_amount=net, fund=compensation.fund)
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not user_has_permission(request.user, "finance.approve"):
            return Response({"detail": "You do not have permission to approve payroll."}, status=status.HTTP_403_FORBIDDEN)
        run = self.get_object()
        if run.status != PayrollRun.Status.DRAFT or not run.items.exists():
            return Response({"detail": "Generate a populated draft payroll first."}, status=status.HTTP_400_BAD_REQUEST)
        run.status = PayrollRun.Status.APPROVED
        run.approved_by = request.user
        run.approved_at = timezone.now()
        run.save(update_fields=["status", "approved_by", "approved_at"])
        return Response(self.get_serializer(run).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def pay(self, request, pk=None):
        if not user_has_permission(request.user, "finance.payroll.pay"):
            return Response({"detail": "You do not have permission to pay payroll."}, status=status.HTTP_403_FORBIDDEN)
        run = self.get_object()
        if run.status != PayrollRun.Status.APPROVED:
            return Response({"detail": "Approve payroll before payment."}, status=status.HTTP_400_BAD_REQUEST)
        payment_date = request.data.get("payment_date") or timezone.localdate().isoformat()
        try:
            paid_on = date.fromisoformat(payment_date)
        except (TypeError, ValueError):
            return Response({"payment_date": ["Invalid payment date."]}, status=status.HTTP_400_BAD_REQUEST)
        run.items.update(paid_on=paid_on)
        run.status = PayrollRun.Status.PAID
        run.paid_at = timezone.now()
        run.save(update_fields=["status", "paid_at"])
        return Response(self.get_serializer(run).data)


class FinanceDashboardAPIView(APIView):
    permission_classes = [HasTenantRole]

    def get(self, request):
        tenant = current_madrasa(request)
        try:
            year = int(request.query_params.get("year", date.today().year))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid year."}, status=status.HTTP_400_BAD_REQUEST)
        funds = Fund.objects.filter(madrasa=tenant, is_active=True)
        budgets = Budget.objects.filter(madrasa=tenant, fiscal_year=year)
        payroll = PayrollRun.objects.filter(madrasa=tenant, month__year=year)
        return Response({
            "year": year,
            "funds": FundSerializer(funds, many=True, context={"request": request}).data,
            "budgets": BudgetSerializer(budgets, many=True, context={"request": request}).data,
            "payroll": PayrollRunSerializer(payroll, many=True, context={"request": request}).data,
        })
