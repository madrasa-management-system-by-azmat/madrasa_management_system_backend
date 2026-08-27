from django.db import migrations, models
import django.db.models.deletion


def seed_existing_papers(apps, schema_editor):
    InternalExam = apps.get_model("exams", "InternalExam")
    InternalExamPaper = apps.get_model("exams", "InternalExamPaper")
    for exam in InternalExam.objects.all():
        subject_ids = list(exam.subjects.values_list("id", flat=True))
        if not subject_ids and exam.subject_id:
            subject_ids = [exam.subject_id]
        for subject_id in subject_ids:
            InternalExamPaper.objects.get_or_create(exam_id=exam.id, subject_id=subject_id, defaults={"paper_date": exam.exam_date})


class Migration(migrations.Migration):
    dependencies = [("exams", "0005_remove_legacy_result_constraint")]

    operations = [
        migrations.CreateModel(name="InternalExamPaper", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("paper_date", models.DateField()),
            ("exam", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="papers", to="exams.internalexam")),
            ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="exam_papers", to="academics.subject")),
        ], options={"ordering": ["paper_date", "subject__academic_class__name", "subject__name"]}),
        migrations.AddConstraint(model_name="internalexampaper", constraint=models.UniqueConstraint(fields=("exam", "subject"), name="unique_exam_subject_paper")),
        migrations.RunPython(seed_existing_papers, migrations.RunPython.noop),
    ]