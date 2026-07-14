import datetime as dt
from zoneinfo import ZoneInfo

from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity, ActivityCategory
from tracking.models import Session
from users.models import UserProfile


class SessionLogForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = (
            "activity",
            "category",
            "local_date",
            "start_time",
            "end_time",
            "duration_minutes",
            "notes",
        )
        widgets = {
            "local_date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user is not None:
            self.instance.user = self.user
            self.fields["category"].queryset = ActivityCategory.objects.filter(
                user=self.user
            )
            activity_qs = Activity.objects.filter(user=self.user)
            if self.is_bound:
                raw_category = self.data.get(self.add_prefix("category"))
                if raw_category:
                    activity_qs = activity_qs.filter(category_id=raw_category)
            elif self.initial.get("category"):
                activity_qs = activity_qs.filter(
                    category_id=self.initial.get("category")
                )
            self.fields["activity"].queryset = activity_qs
            if not self.is_bound and not self.initial.get("local_date"):
                tz_name = (
                    UserProfile.objects.filter(user=self.user)
                    .values_list("timezone", flat=True)
                    .first()
                    or "UTC"
                )
                tz = ZoneInfo(tz_name)
                self.initial["local_date"] = dt.datetime.now(tz).date()
        if (
            self.instance
            and self.instance.activity_id
            and not self.instance.category_id
        ):
            self.initial.setdefault("category", self.instance.activity.category_id)

    def clean(self):
        cleaned = super().clean()
        activity = cleaned.get("activity")
        category = cleaned.get("category")
        local_date = cleaned.get("local_date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        duration_minutes = cleaned.get("duration_minutes")

        if not local_date:
            raise ValidationError("Date is required.")

        if not category:
            raise ValidationError("Category is required.")
        if not activity:
            raise ValidationError("Activity is required.")
        if activity and category and activity.category_id != category.id:
            raise ValidationError("Activity must belong to the selected category.")

        if end_time and not start_time:
            raise ValidationError("Start time is required when end time is provided.")

        if not start_time and not end_time and not duration_minutes:
            raise ValidationError("Provide a time range or duration.")

        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError("End time must be after start time.")
            delta = dt.datetime.combine(local_date, end_time) - dt.datetime.combine(
                local_date, start_time
            )
            cleaned["duration_minutes"] = int(delta.total_seconds() // 60)
        elif start_time and not duration_minutes:
            raise ValidationError("Provide an end time or duration.")

        tz_name = "UTC"
        if self.user is not None:
            tz_name = (
                UserProfile.objects.filter(user=self.user)
                .values_list("timezone", flat=True)
                .first()
                or "UTC"
            )
        tz = ZoneInfo(tz_name)

        if start_time:
            local_start = dt.datetime.combine(local_date, start_time, tzinfo=tz)
            cleaned["start"] = local_start.astimezone(dt.timezone.utc)
        else:
            cleaned["start"] = None

        if start_time and end_time:
            local_end = dt.datetime.combine(local_date, end_time, tzinfo=tz)
            cleaned["end"] = local_end.astimezone(dt.timezone.utc)
        else:
            cleaned["end"] = None

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.start = self.cleaned_data.get("start")
        instance.end = self.cleaned_data.get("end")
        if commit:
            instance.save()
        return instance
