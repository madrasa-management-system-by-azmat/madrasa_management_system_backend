from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("academics", "0001_initial")]

    operations = [
        migrations.AddField(model_name="subject", name="total_marks", field=models.PositiveIntegerField(default=100)),
        migrations.AddField(model_name="subject", name="passing_marks", field=models.PositiveIntegerField(default=40)),
    ]