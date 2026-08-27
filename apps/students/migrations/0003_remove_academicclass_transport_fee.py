from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("students", "0002_academicclass_fee_rates")]

    operations = [
        migrations.RemoveField(model_name="academicclass", name="transport_fee"),
    ]