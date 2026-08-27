from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finance", "0002_teachersalary"), ("students", "0002_academicclass_fee_rates")]

    operations = [
        migrations.CreateModel(name="StudentMonthlyFee", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("month", models.DateField(help_text="First day of the billed month.")),
            ("tuition_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("hostel_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("transport_fee", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("previous_balance", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("due_date", models.DateField()),
            ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monthly_fees", to="students.student")),
        ], options={"ordering": ["-month", "student__full_name"]}),
        migrations.CreateModel(name="StudentFeePayment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
            ("payment_date", models.DateField()),
            ("receipt_number", models.CharField(blank=True, max_length=60)),
            ("notes", models.TextField(blank=True)),
            ("monthly_fee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="finance.studentmonthlyfee")),
        ], options={"ordering": ["-payment_date", "-id"]}),
        migrations.AddConstraint(model_name="studentmonthlyfee", constraint=models.UniqueConstraint(fields=("student", "month"), name="unique_student_monthly_fee")),
    ]