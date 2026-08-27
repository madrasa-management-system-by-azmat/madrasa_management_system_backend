from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("exams", "0006_internal_exam_papers")]

    operations = [
        migrations.AddField(model_name="internalexampaper", name="paper_time", field=models.TimeField(blank=True, null=True)),
        migrations.AlterModelOptions(name="internalexampaper", options={"ordering": ["paper_date", "paper_time", "subject__academic_class__name", "subject__name"]}),
    ]