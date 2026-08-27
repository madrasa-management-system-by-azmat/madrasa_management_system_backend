from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial"), ("staff", "0002_staff_photo")]

    operations = [
        migrations.CreateModel(
            name="TeacherSalary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.DateField(help_text="Use the first day of the salary month.")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("is_paid", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="salary_records", to="staff.staff")),
            ],
            options={"ordering": ["-month", "teacher__full_name"]},
        ),
        migrations.AddConstraint(model_name="teachersalary", constraint=models.UniqueConstraint(fields=("teacher", "month"), name="unique_teacher_salary_per_month")),
    ]