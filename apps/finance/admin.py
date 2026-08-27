from django.contrib import admin

from .models import Donation, Donor, Expense, Fund, StudentFeeLog, StudentSponsorship

admin.site.register(Fund)
admin.site.register(Donor)
admin.site.register(Donation)
admin.site.register(StudentFeeLog)
admin.site.register(StudentSponsorship)
admin.site.register(Expense)
