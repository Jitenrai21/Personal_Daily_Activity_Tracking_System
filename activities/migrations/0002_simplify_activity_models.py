from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="activitycategory",
            name="color",
        ),
        migrations.RemoveField(
            model_name="activitycategory",
            name="is_default",
        ),
        migrations.RemoveField(
            model_name="activitycategory",
            name="is_archived",
        ),
        migrations.RemoveField(
            model_name="activity",
            name="target_type",
        ),
        migrations.RemoveField(
            model_name="activity",
            name="target_value",
        ),
        migrations.RemoveField(
            model_name="activity",
            name="is_active",
        ),
    ]
