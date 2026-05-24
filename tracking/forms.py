import datetime as dt

from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity
from tracking.models import Session


class SessionLogForm(forms.ModelForm):
    duration_minutes = forms.IntegerField(min_value=1, required=False)

    class Meta:
        model = Session
        fields = ("activity", "start", "end", "notes")
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user is not None:
            self.instance.user = self.user
            self.fields["activity"].queryset = Activity.objects.filter(user=self.user)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")
        duration_minutes = cleaned.get("duration_minutes")

        if not start:
            raise ValidationError("Start time is required.")

        if not end and not duration_minutes:
            raise ValidationError("Provide an end time or duration.")

        if end and duration_minutes:
            computed_end = start + dt.timedelta(minutes=duration_minutes)
            if computed_end != end:
                raise ValidationError(
                    "End time does not match the provided duration."
                )

        if not end and duration_minutes:
            cleaned["end"] = start + dt.timedelta(minutes=duration_minutes)

        end = cleaned.get("end")
        if end and end <= start:
            raise ValidationError("End time must be after start time.")

        return cleaned
