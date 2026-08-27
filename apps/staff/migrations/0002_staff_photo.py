from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staff", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="staff/photos/"),
        ),
    ]