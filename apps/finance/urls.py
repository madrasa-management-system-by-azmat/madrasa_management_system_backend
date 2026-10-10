from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import BudgetViewSet, DonationViewSet, DonorViewSet, ExpenseViewSet, FinanceDashboardAPIView, FinanceLedgerAPIView, FinanceYearlyReportAPIView, FinancialCategoryViewSet, FundTransferViewSet, FundViewSet, PayrollRunViewSet, StaffCompensationViewSet, StudentFeeLogViewSet, StudentFeePaymentViewSet, StudentMonthlyFeeViewSet, StudentSponsorshipViewSet, TeacherSalaryViewSet

router = DefaultRouter()
router.register("funds", FundViewSet, basename="fund")
router.register("donors", DonorViewSet, basename="donor")
router.register("donations", DonationViewSet, basename="donation")
router.register("student-fee-logs", StudentFeeLogViewSet, basename="student-fee-log")
router.register("monthly-fees", StudentMonthlyFeeViewSet, basename="monthly-fee")
router.register("fee-payment-history", StudentFeePaymentViewSet, basename="fee-payment-history")
router.register("teacher-salaries", TeacherSalaryViewSet, basename="teacher-salary")
router.register("student-sponsorships", StudentSponsorshipViewSet, basename="student-sponsorship")
router.register("expenses", ExpenseViewSet, basename="expense")
router.register("financial-categories", FinancialCategoryViewSet, basename="financial-category")
router.register("fund-transfers", FundTransferViewSet, basename="fund-transfer")
router.register("budgets", BudgetViewSet, basename="budget")
router.register("staff-compensations", StaffCompensationViewSet, basename="staff-compensation")
router.register("payroll-runs", PayrollRunViewSet, basename="payroll-run")

urlpatterns = [
	path("finance-ledger/", FinanceLedgerAPIView.as_view(), name="finance-ledger"),
	path("finance-yearly-report/", FinanceYearlyReportAPIView.as_view(), name="finance-yearly-report"),
	path("finance-dashboard/", FinanceDashboardAPIView.as_view(), name="finance-dashboard"),
] + router.urls
