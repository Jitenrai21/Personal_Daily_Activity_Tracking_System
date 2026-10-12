from django.core.exceptions import ValidationError
from django.db import models

CATEGORY_COLOR_PALETTE = (  # noqa: RUF012
    "#3CB371",  # green (chart actual top)
    "#F0A500",  # amber (chart planned bottom)
    "#9c6669",  # dusty rose (KPI activity-streak icon)
    "#6d6593",  # periwinkle (KPI plan-streak icon)
    "#5685e8",  # blue (info token)
    "#3f8f6b",  # deep green (success token)
)

CATEGORY_NO_COLOR = "#9aa79c"


class ActivityCategory(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, blank=True, default="")

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["user", "name"], name="unique_category_per_user"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.color:
            used = (
                ActivityCategory.objects.filter(user=self.user)
                .exclude(pk=self.pk)
                .count()
            )
            self.color = CATEGORY_COLOR_PALETTE[used % len(CATEGORY_COLOR_PALETTE)]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Activity(models.Model):
    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    category = models.ForeignKey(
        ActivityCategory, on_delete=models.PROTECT, related_name="activities"
    )
    title = models.CharField(max_length=200)
    weight = models.PositiveSmallIntegerField(default=3)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return self.title


class RecurrenceRule(models.Model):
    FREQ_DAILY = "daily"
    FREQ_WEEKLY = "weekly"
    FREQ_MONTHLY = "monthly"
    FREQ_CHOICES = [  # noqa: RUF012
        (FREQ_DAILY, "Daily"),
        (FREQ_WEEKLY, "Weekly"),
        (FREQ_MONTHLY, "Monthly"),
    ]

    activity = models.OneToOneField(
        Activity, on_delete=models.CASCADE, related_name="recurrence"
    )
    frequency = models.CharField(max_length=20, choices=FREQ_CHOICES)
    interval = models.PositiveIntegerField(default=1)
    weekdays = models.JSONField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    exceptions = models.JSONField(blank=True, null=True)

    def clean(self) -> None:
        if self.interval < 1:
            raise ValidationError({"interval": "Interval must be >= 1."})

        if self.frequency == self.FREQ_WEEKLY and not self.weekdays:
            raise ValidationError({"weekdays": "Weekdays are required."})

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def __str__(self) -> str:
        return f"{self.activity.title} ({self.frequency})"
