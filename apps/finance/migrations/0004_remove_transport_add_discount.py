from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_monthly_fee_ledger")]

    operations = [
        migrations.RemoveField(model_name="studentmonthlyfee", name="transport_fee"),
        migrations.AddField(model_name="studentmonthlyfee", name="discount", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
    ]