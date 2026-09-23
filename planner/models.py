import datetime as dt

from django.core.exceptions import ValidationError
from django.db import models

from activities.models import Activity, ActivityCategory


class ScheduleBlock(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    category = models.ForeignKey(
        ActivityCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]  # noqa: RUF012

    def clean(self) -> None:
        if self.end_time and not self.start_time:
            raise ValidationError(
                {"start_time": "Start time is required when end time is provided."}
            )
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

        if not self.start_time and not self.end_time and not self.duration_minutes:
            raise ValidationError("Provide a time range or duration.")

    def save(self, *args, **kwargs):
        if self.activity and not self.category:
            self.category = self.activity.category
        if self.duration_minutes is None and self.start_time and self.end_time:
            delta = dt.datetime.combine(self.date, self.end_time) - dt.datetime.combine(
                self.date, self.start_time
            )
            self.duration_minutes = int(delta.total_seconds() // 60)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.activity.title} on {self.date}"
