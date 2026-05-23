from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    wake_time = models.TimeField(null=True, blank=True)
    sleep_time = models.TimeField(null=True, blank=True)
    sleep_target_minutes = models.PositiveIntegerField(default=480)
    daily_focus_minutes = models.PositiveIntegerField(default=120)
    weekly_goal_minutes = models.PositiveIntegerField(default=600)

    def __str__(self) -> str:
        return f"Profile for {self.user.username}"
