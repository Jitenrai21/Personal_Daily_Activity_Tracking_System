from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("analytics", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyScore",
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
                ("local_date", models.DateField()),
                ("discipline_score", models.FloatField(default=0)),
                ("balance_score", models.FloatField(default=0)),
                ("recovery_score", models.FloatField(default=0)),
                ("composite_score", models.FloatField(default=0)),
                ("version", models.CharField(default="v1", max_length=20)),
                ("computed_at", models.DateTimeField(auto_now=True)),
                ("explanation_json", models.JSONField(blank=True, default=dict)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-local_date"]},
        ),
        migrations.CreateModel(
            name="DailyReflection",
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
                ("local_date", models.DateField()),
                ("prompt_text", models.TextField()),
                ("answer_text", models.TextField(blank=True)),
                (
                    "mood",
                    models.CharField(
                        choices=[
                            ("great", "Great"),
                            ("good", "Good"),
                            ("neutral", "Neutral"),
                            ("low", "Low"),
                        ],
                        default="neutral",
                        max_length=20,
                    ),
                ),
                ("tags", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-local_date"]},
        ),
        migrations.AddConstraint(
            model_name="dailyscore",
            constraint=models.UniqueConstraint(
                fields=("user", "local_date"),
                name="unique_daily_score_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="dailyreflection",
            constraint=models.UniqueConstraint(
                fields=("user", "local_date"),
                name="unique_daily_reflection_per_user",
            ),
        ),
    ]
