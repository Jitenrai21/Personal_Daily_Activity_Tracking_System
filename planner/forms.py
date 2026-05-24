import datetime as dt

from django import forms
from django.core.exceptions import ValidationError

from planner.models import ScheduleBlock, WeeklyRoutine
from users.models import UserProfile


class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = (
            "activity",
            "date",
            "start_time",
            "end_time",
            "source",
            "is_recurring",
            "notes",
        )
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.instance.user = self.user
            self.fields["activity"].queryset = self.user.activity_set.all()
            profile = UserProfile.objects.filter(user=self.user).first()
            if profile:
                self.instance.timezone = profile.timezone

    def clean(self):
        cleaned = super().clean()
        if not self.user:
            return cleaned

        profile = UserProfile.objects.filter(user=self.user).first()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")

        if profile and profile.wake_time and profile.sleep_time and start and end:
            if start < profile.wake_time or end > profile.sleep_time:
                raise ValidationError(
                    "Schedule block must fall within your wake/sleep window."
                )

        return cleaned


class WeeklyRoutineForm(forms.ModelForm):
    class Meta:
        model = WeeklyRoutine
        fields = (
            "activity",
            "weekday",
            "start_time",
            "end_time",
            "notes",
            "is_active",
        )
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.instance.user = self.user
            self.fields["activity"].queryset = self.user.activity_set.all()

    def clean(self):
        cleaned = super().clean()
        weekday = cleaned.get("weekday")
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")

        if weekday is not None and (weekday < 0 or weekday > 6):
            self.add_error("weekday", "Weekday must be between 0 and 6.")

        if start and end and end <= start:
            self.add_error("end_time", "End time must be after start time.")

        return cleaned
