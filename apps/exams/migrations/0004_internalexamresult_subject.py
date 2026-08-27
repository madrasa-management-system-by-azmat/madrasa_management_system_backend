from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("exams", "0003_internalexam_subjects"), ("academics", "0001_initial")]

    operations = [
        migrations.AddField(model_name="internalexamresult", name="subject", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="exam_results", to="academics.subject")),
        migrations.AddConstraint(model_name="internalexamresult", constraint=models.UniqueConstraint(fields=("exam", "student", "subject"), name="unique_internal_result_per_subject")),
    ]