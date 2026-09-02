from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_normalize_legacy_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="madrasaprofile",
            name="primary_color",
            field=models.CharField(default="#226CE0", max_length=7),
        ),
        migrations.AddField(
            model_name="madrasaprofile",
            name="sidebar_color",
            field=models.CharField(default="#172554", max_length=7),
        ),
    ]