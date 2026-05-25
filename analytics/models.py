from django.db import models


class AggregatedDaily(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    date = models.DateField()
    total_minutes = models.PositiveIntegerField(default=0)
    planned_minutes = models.PositiveIntegerField(default=0)
    completion_rate = models.FloatField(null=True, blank=True)
    sessions_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="unique_daily_per_user"
            )
        ]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.user.username} - {self.date}"


class DailyScore(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    local_date = models.DateField()
    discipline_score = models.FloatField(default=0)
    balance_score = models.FloatField(default=0)
    recovery_score = models.FloatField(default=0)
    composite_score = models.FloatField(default=0)
    version = models.CharField(max_length=20, default="v1")
    computed_at = models.DateTimeField(auto_now=True)
    explanation_json = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "local_date"], name="unique_daily_score_per_user"
            )
        ]
        ordering = ["-local_date"]

    def __str__(self) -> str:
        return f"{self.user.username} score {self.local_date}"


class DailyReflection(models.Model):
    MOOD_CHOICES = [
        ("great", "Great"),
        ("good", "Good"),
        ("neutral", "Neutral"),
        ("low", "Low"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    local_date = models.DateField()
    prompt_text = models.TextField()
    answer_text = models.TextField(blank=True)
    mood = models.CharField(max_length=20, choices=MOOD_CHOICES, default="neutral")
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "local_date"],
                name="unique_daily_reflection_per_user",
            )
        ]
        ordering = ["-local_date"]

    def __str__(self) -> str:
        return f"{self.user.username} reflection {self.local_date}"
