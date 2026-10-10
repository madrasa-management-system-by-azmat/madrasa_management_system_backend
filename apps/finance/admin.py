from django.contrib import admin

from .models import Budget, BudgetLine, Donation, Donor, Expense, FinancialCategory, Fund, FundTransfer, PayrollItem, PayrollRun, StaffCompensation, StudentFeeLog, StudentFeePayment, StudentMonthlyFee, StudentSponsorship, TeacherSalary

admin.site.register(Fund)
admin.site.register(Donor)
admin.site.register(Donation)
admin.site.register(StudentFeeLog)
admin.site.register(StudentSponsorship)
admin.site.register(Expense)
admin.site.register(FinancialCategory)
admin.site.register(FundTransfer)
admin.site.register(Budget)
admin.site.register(BudgetLine)
admin.site.register(StaffCompensation)
admin.site.register(PayrollRun)
admin.site.register(PayrollItem)
admin.site.register(StudentMonthlyFee)
admin.site.register(StudentFeePayment)
admin.site.register(TeacherSalary)
