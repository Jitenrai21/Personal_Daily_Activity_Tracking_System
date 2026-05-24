from django.core.exceptions import ValidationError
from django.db import models

from activities.models import Activity


class WeeklyRoutine(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]

    def clean(self) -> None:
        if self.weekday > 6:
            raise ValidationError({"weekday": "Weekday must be between 0 and 6."})
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

    def __str__(self) -> str:
        return f"{self.activity.title} (weekday {self.weekday})"


class ScheduleBlock(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_ROUTINE = "routine"
    SOURCE_GENERATED = "generated"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_ROUTINE, "Routine"),
        (SOURCE_GENERATED, "Generated"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=64, default="Asia/Kathmandu")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    is_recurring = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]

    def clean(self) -> None:
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

        if not self.user_id:
            return

        overlaps = (
            ScheduleBlock.objects.filter(user=self.user, date=self.date)
            .exclude(pk=self.pk)
            .filter(start_time__lt=self.end_time, end_time__gt=self.start_time)
        )

        if overlaps.exists():
            raise ValidationError("This block overlaps with another scheduled block.")

    def __str__(self) -> str:
        return f"{self.activity.title} on {self.date}"
