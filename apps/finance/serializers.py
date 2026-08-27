from rest_framework import serializers

from .models import Donation, Donor, Expense, Fund, StudentFeeLog, StudentFeePayment, StudentMonthlyFee, StudentSponsorship, TeacherSalary


class FundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fund
        fields = ["id", "name", "fund_type", "restriction"]


class DonorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Donor
        fields = ["id", "full_name", "phone", "address"]


class DonationSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.full_name", read_only=True)
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = Donation
        fields = ["id", "donor", "donor_name", "fund", "fund_name", "amount", "date", "receipt_number"]


class StudentFeeLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = StudentFeeLog
        fields = ["id", "student", "student_name", "amount_due", "due_date", "is_paid"]


class StudentFeePaymentSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source="monthly_fee.student_id", read_only=True)
    student_name = serializers.CharField(source="monthly_fee.student.full_name", read_only=True)
    registration_number = serializers.CharField(source="monthly_fee.student.registration_number", read_only=True)
    academic_class_name = serializers.CharField(source="monthly_fee.student.current_class.name", read_only=True)
    billing_month = serializers.DateField(source="monthly_fee.month", read_only=True)

    class Meta:
        model = StudentFeePayment
        fields = ["id", "monthly_fee", "student", "student_name", "registration_number", "academic_class_name", "billing_month", "amount", "payment_date", "receipt_number", "notes"]


class StudentMonthlyFeeSerializer(serializers.ModelSerializer):
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


class TeacherSalarySerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.full_name", read_only=True)

    class Meta:
        model = TeacherSalary
        fields = ["id", "teacher", "teacher_name", "month", "amount", "payment_date", "is_paid", "notes"]


class StudentSponsorshipSerializer(serializers.ModelSerializer):
    donor_name = serializers.CharField(source="donor.full_name", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = StudentSponsorship
        fields = ["id", "donor", "donor_name", "student", "student_name", "fund", "fund_name", "start_date", "end_date"]


class ExpenseSerializer(serializers.ModelSerializer):
    fund_name = serializers.CharField(source="fund.name", read_only=True)

    class Meta:
        model = Expense
        fields = ["id", "title", "amount", "date", "fund", "fund_name"]
