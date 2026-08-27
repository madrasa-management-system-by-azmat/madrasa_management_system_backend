from django.db import migrations


def normalize_roles(apps, schema_editor):
    UserProfile = apps.get_model("users", "UserProfile")
    UserProfile.objects.exclude(role__in=["admin", "operator", "accountant"]).update(role="operator")


class Migration(migrations.Migration):
    dependencies = [("users", "0005_backfill_initial_madrasa_tenant")]
    operations = [migrations.RunPython(normalize_roles, migrations.RunPython.noop)]