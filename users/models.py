from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    timezone = models.CharField(max_length=64, default="UTC")
    wake_time = models.TimeField(null=True, blank=True)
    sleep_target_minutes = models.PositiveIntegerField(default=480)

    def __str__(self) -> str:
        return f"Profile for {self.user.username}"
