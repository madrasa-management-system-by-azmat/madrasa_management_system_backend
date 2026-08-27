from django.db import migrations, models


def copy_existing_class_to_classes(apps, schema_editor):
    InternalExam = apps.get_model("exams", "InternalExam")
    for exam in InternalExam.objects.exclude(academic_class__isnull=True):
        exam.classes.add(exam.academic_class_id)


class Migration(migrations.Migration):
    dependencies = [("exams", "0001_initial")]

    operations = [
        migrations.AlterField(model_name="internalexam", name="academic_class", field=models.ForeignKey(blank=True, null=True, on_delete=models.CASCADE, related_name="internal_exams", to="students.academicclass")),
        migrations.AddField(model_name="internalexam", name="classes", field=models.ManyToManyField(blank=True, related_name="multi_class_internal_exams", to="students.academicclass")),
        migrations.RunPython(copy_existing_class_to_classes, migrations.RunPython.noop),
    ]