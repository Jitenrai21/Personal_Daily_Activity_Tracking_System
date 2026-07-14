import datetime as dt

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from activities.models import Activity, ActivityCategory


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
    activity = models.ForeignKey(
        Activity, on_delete=models.SET_NULL, null=True, blank=True
    )
    category = models.ForeignKey(
        ActivityCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    local_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    paused_seconds = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-local_date", "-start"]
        indexes = [
            models.Index(fields=["user", "start"]),
            models.Index(fields=["user", "local_date"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self) -> None:
        if self.start and self.end and self.end <= self.start:
            raise ValidationError({"end": "End time must be after start time."})

        if (
            self.start_time
            and self.end_time
            and (self.start is None or self.end is None)
            and self.end_time <= self.start_time
        ):
            raise ValidationError({"end_time": "End time must be after start time."})

    @property
    def duration(self):
        if self.duration_minutes is not None:
            return dt.timedelta(minutes=self.duration_minutes)

        if self.start and self.end:
            return self.end - self.start
        return None

    @property
    def timer_state(self) -> str:
        if self.end is not None:
            return "stopped"

        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        state = metadata.get("timer_state")
        if state in {"running", "paused"}:
            return state
        if self.source == self.SOURCE_TIMER:
            return "running"
        return "stopped"

    @property
    def is_paused(self) -> bool:
        return self.timer_state == "paused"

    @property
    def paused_at(self):
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        paused_at = metadata.get("paused_at")
        if not paused_at:
            return None
        try:
            return dt.datetime.fromisoformat(paused_at)
        except ValueError:
            return None

    @property
    def timer_elapsed_seconds(self) -> int:
        if not self.start:
            return 0

        effective_end = self.end or self.paused_at or timezone.now()
        elapsed = (effective_end - self.start).total_seconds() - (
            self.paused_seconds or 0
        )
        return max(0, int(elapsed))

    def save(self, *args, **kwargs):
        if self.duration_minutes is None:
            if self.start and self.end:
                seconds = (self.end - self.start).total_seconds() - (
                    self.paused_seconds or 0
                )
                self.duration_minutes = max(0, int(seconds // 60))
            elif self.local_date and self.start_time and self.end_time:
                start_dt = dt.datetime.combine(self.local_date, self.start_time)
                end_dt = dt.datetime.combine(self.local_date, self.end_time)
                seconds = (end_dt - start_dt).total_seconds()
                self.duration_minutes = int(seconds // 60)

        super().save(*args, **kwargs)

    @property
    def is_running(self) -> bool:
        return (
            self.end is None and self.source == self.SOURCE_TIMER and not self.is_paused
        )

    def __str__(self) -> str:
        label = self.activity.title if self.activity else "Unassigned"
        return f"{label} ({self.local_date})"
