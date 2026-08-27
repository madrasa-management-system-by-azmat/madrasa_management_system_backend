from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("exams", "0004_internalexamresult_subject")]

    operations = [
        migrations.RemoveConstraint(model_name="internalexamresult", name="unique_internal_result_per_student"),
    ]