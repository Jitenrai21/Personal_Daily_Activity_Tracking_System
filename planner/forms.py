import datetime as dt

from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity, ActivityCategory
from planner.models import ScheduleBlock


class PlannerCategoryForm(forms.ModelForm):
    class Meta:
        model = ActivityCategory
        fields = ("name", "description")
        widgets = {  # noqa: RUF012
            "description": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Optional description"}
            ),
        }


class PlannerActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ("category", "title", "weight", "notes")
        widgets = {  # noqa: RUF012
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["category"].queryset = ActivityCategory.objects.filter(
                user=self.user
            )


class ScheduleBlockForm(forms.ModelForm):
    class Meta:
        model = ScheduleBlock
        fields = (
            "activity",
            "category",
            "date",
            "start_time",
            "end_time",
            "duration_minutes",
            "notes",
        )
        widgets = {  # noqa: RUF012
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
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
            if not self.is_bound and not self.initial.get("date"):
                self.initial["date"] = dt.datetime.now(dt.timezone.utc).date()
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
        date = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        duration_minutes = cleaned.get("duration_minutes")

        if not date:
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
            delta = dt.datetime.combine(date, end_time) - dt.datetime.combine(
                date, start_time
            )
            cleaned["duration_minutes"] = int(delta.total_seconds() // 60)
        elif start_time and not duration_minutes:
            raise ValidationError("Provide an end time or duration.")

        return cleaned
