from datetime import date
from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Donation, Donor, Expense, Fund, StudentFeeLog, StudentFeePayment, StudentMonthlyFee, StudentSponsorship, TeacherSalary
from .serializers import DonationSerializer, DonorSerializer, ExpenseSerializer, FundSerializer, StudentFeeLogSerializer, StudentFeePaymentSerializer, StudentMonthlyFeeSerializer, StudentSponsorshipSerializer, TeacherSalarySerializer
from apps.users.permissions import HasTenantRole
from apps.users.tenancy import TenantScopedViewSetMixin, current_madrasa


class FinanceViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


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
        if not month_value or not due_date or not academic_class:
            return Response({"detail": "month, due_date, and academic_class are required."}, status=status.HTTP_400_BAD_REQUEST)
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
            for student in Student.objects.filter(madrasa=tenant, status="active", current_class_id=academic_class).select_related("current_class"):
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
            student = Student.objects.filter(madrasa=tenant, pk=student_id, current_class_id=academic_class).first()
            if not student:
                return Response({"detail": "Invalid student for this madrasa or class."}, status=status.HTTP_400_BAD_REQUEST)
            _, was_created = StudentMonthlyFee.objects.get_or_create(
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
        return Response({"created": created, "month": billing_month}, status=status.HTTP_201_CREATED)

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
    queryset = Expense.objects.select_related("fund")
    serializer_class = ExpenseSerializer
    search_fields = ["title", "fund__name"]
    ordering_fields = ["date", "amount", "title"]
