from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="MadrasaProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=250)),
                ("name_english", models.CharField(blank=True, max_length=250)),
                ("logo", models.ImageField(blank=True, null=True, upload_to="madrasa/logo/")),
                ("address", models.TextField(blank=True)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("province", models.CharField(blank=True, max_length=120)),
                ("country", models.CharField(blank=True, default="Pakistan", max_length=120)),
                ("postal_code", models.CharField(blank=True, max_length=20)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("alternate_phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("website", models.URLField(blank=True)),
                ("principal_name", models.CharField(blank=True, max_length=200)),
                ("principal_title", models.CharField(blank=True, max_length=120)),
                ("registration_number", models.CharField(blank=True, max_length=100)),
                ("established_year", models.PositiveIntegerField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Madrasa profile", "verbose_name_plural": "Madrasa profile"},
        )
    ]