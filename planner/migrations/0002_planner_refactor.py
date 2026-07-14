import datetime as dt

from django.db import migrations, models
import django.db.models.deletion


def backfill_schedule_blocks(apps, schema_editor):
    ScheduleBlock = apps.get_model("planner", "ScheduleBlock")
    Activity = apps.get_model("activities", "Activity")

    for block in ScheduleBlock.objects.all().iterator():
        if block.activity_id:
            activity = Activity.objects.filter(pk=block.activity_id).first()
            block.category_id = activity.category_id if activity else None

        if block.start_time and block.end_time:
            delta = dt.datetime.combine(
                block.date, block.end_time
            ) - dt.datetime.combine(block.date, block.start_time)
            block.duration_minutes = int(delta.total_seconds() // 60)

        block.save(update_fields=["category", "duration_minutes"])


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0001_initial"),
        ("planner", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduleblock",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="activities.activitycategory",
            ),
        ),
        migrations.AddField(
            model_name="scheduleblock",
            name="duration_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="scheduleblock",
            name="start_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="scheduleblock",
            name="end_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.RemoveField(
            model_name="scheduleblock",
            name="timezone",
        ),
        migrations.RemoveField(
            model_name="scheduleblock",
            name="source",
        ),
        migrations.RemoveField(
            model_name="scheduleblock",
            name="is_recurring",
        ),
        migrations.RunPython(backfill_schedule_blocks, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="WeeklyRoutine",
        ),
    ]
