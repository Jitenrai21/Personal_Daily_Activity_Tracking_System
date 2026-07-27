import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def backfill_session_fields(apps, schema_editor):
    Session = apps.get_model("tracking", "Session")
    Activity = apps.get_model("activities", "Activity")

    for session in Session.objects.all().iterator():
        if session.activity_id:
            activity = Activity.objects.filter(pk=session.activity_id).first()
            session.category_id = activity.category_id if activity else None

        if session.start:
            start = session.start
            if timezone.is_aware(start):
                start = start.astimezone(timezone.utc)
            session.local_date = start.date()
            session.start_time = start.time().replace(microsecond=0)

        if session.end:
            end = session.end
            if timezone.is_aware(end):
                end = end.astimezone(timezone.utc)
            session.end_time = end.time().replace(microsecond=0)
            duration = session.end - session.start
            session.duration_minutes = int(duration.total_seconds() // 60)

        session.save(
            update_fields=[
                "category",
                "local_date",
                "start_time",
                "end_time",
                "duration_minutes",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [  # noqa: RUF012
        ("activities", "0001_initial"),
        ("tracking", "0001_initial"),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name="session",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="activities.activitycategory",
            ),
        ),
        migrations.AddField(
            model_name="session",
            name="local_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="session",
            name="start_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="session",
            name="end_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="session",
            name="duration_minutes",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="session",
            name="start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_session_fields, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="session",
            name="local_date",
            field=models.DateField(),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(
                fields=["user", "local_date"], name="tracking_se_user_id_local_date_idx"
            ),
        ),
    ]
