from django.db import models


class Activity(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=100)
    default_target_seconds = models.PositiveIntegerField(default=0)
    priority = models.PositiveSmallIntegerField(default=3)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.title
