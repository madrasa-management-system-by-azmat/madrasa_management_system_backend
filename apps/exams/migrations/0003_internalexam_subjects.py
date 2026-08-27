from django.db import migrations, models


def copy_existing_subject_to_subjects(apps, schema_editor):
    InternalExam = apps.get_model("exams", "InternalExam")
    for exam in InternalExam.objects.exclude(subject__isnull=True):
        exam.subjects.add(exam.subject_id)


class Migration(migrations.Migration):
    dependencies = [("exams", "0002_internalexam_classes")]

    operations = [
        migrations.AlterField(model_name="internalexam", name="subject", field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name="internal_exams", to="academics.subject")),
        migrations.AddField(model_name="internalexam", name="subjects", field=models.ManyToManyField(blank=True, related_name="multi_subject_internal_exams", to="academics.subject")),
        migrations.RunPython(copy_existing_subject_to_subjects, migrations.RunPython.noop),
    ]