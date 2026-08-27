from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0002_madrasaprofile")]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="users/photos/"),
        )
    ]