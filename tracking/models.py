from django.core.exceptions import ValidationError
from django.db import models

from activities.models import Activity


class Session(models.Model):
    SOURCE_TIMER = "timer"
    SOURCE_MANUAL = "manual"
    SOURCE_IMPORT = "import"
    SOURCE_CHOICES = [
        (SOURCE_TIMER, "Timer"),
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_IMPORT, "Import"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start"]
        indexes = [
            models.Index(fields=["user", "start"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self) -> None:
        if self.end and self.end <= self.start:
            raise ValidationError({"end": "End time must be after start time."})

    @property
    def duration(self):
        if not self.end:
            return None
        return self.end - self.start

    @property
    def duration_minutes(self):
        duration = self.duration
        if duration is None:
            return None
        return int(duration.total_seconds() // 60)

    @property
    def is_running(self) -> bool:
        return self.end is None

    def __str__(self) -> str:
        label = self.activity.title if self.activity else "Unassigned"
        return f"{label} ({self.start})"
