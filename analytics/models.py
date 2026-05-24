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
