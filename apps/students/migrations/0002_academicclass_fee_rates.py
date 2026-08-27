from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("students", "0001_initial")]

    operations = [
        migrations.AddField(model_name="academicclass", name="tuition_fee", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name="academicclass", name="hostel_fee", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name="academicclass", name="transport_fee", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
    ]