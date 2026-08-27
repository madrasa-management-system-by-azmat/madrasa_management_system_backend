from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("students", "0005_academicclass_madrasa_department_madrasa_and_more")]

    operations = [
        migrations.AddField(model_name="student", name="admission_decision", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="student", name="admission_test_report", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="caste", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="student", name="country", field=models.CharField(blank=True, default="پاکستان", max_length=100)),
        migrations.AddField(model_name="student", name="current_address", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="guardian_cnic", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="student", name="guardian_phone", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="student", name="guardian_relation", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="student", name="health_conditions", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="modern_education", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="nationality", field=models.CharField(blank=True, default="پاکستانی", max_length=100)),
        migrations.AddField(model_name="student", name="office_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="other_certificates", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="permanent_address", field=models.TextField(blank=True)),
        migrations.AddField(model_name="student", name="previous_madrasas", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="student", name="relatives", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="student", name="religion", field=models.CharField(blank=True, default="اسلام", max_length=100)),
        migrations.AddField(model_name="student", name="requested_class", field=models.CharField(blank=True, max_length=150)),
    ]