import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [  # noqa: RUF012
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [  # noqa: RUF012
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("wake_time", models.TimeField(blank=True, null=True)),
                ("sleep_time", models.TimeField(blank=True, null=True)),
                (
                    "sleep_target_minutes",
                    models.PositiveIntegerField(default=480),
                ),
                (
                    "daily_focus_minutes",
                    models.PositiveIntegerField(default=120),
                ),
                (
                    "weekly_goal_minutes",
                    models.PositiveIntegerField(default=600),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
