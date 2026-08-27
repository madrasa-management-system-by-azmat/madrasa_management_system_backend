from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("students", "0003_remove_academicclass_transport_fee")]

    operations = [
        migrations.CreateModel(
            name="StudentAttendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("status", models.CharField(choices=[("present", "حاضر"), ("absent", "غیر حاضر"), ("leave", "رخصت")], default="present", max_length=10)),
                ("remarks", models.CharField(blank=True, max_length=255)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance_records", to="students.student")),
            ],
            options={"ordering": ["-date", "student__full_name"]},
        ),
        migrations.AddConstraint(
            model_name="studentattendance",
            constraint=models.UniqueConstraint(fields=("student", "date"), name="unique_student_attendance_per_day"),
        ),
    ]