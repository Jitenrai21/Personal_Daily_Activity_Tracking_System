from django import forms

from activities.models import Activity, ActivityCategory, RecurrenceRule


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ActivityCategory
        fields = ("name", "description")


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = (
            "category",
            "title",
            "weight",
            "notes",
        )
        widgets = {  # noqa: RUF012
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = ActivityCategory.objects.filter(
                user=user
            )


class RecurrenceRuleForm(forms.ModelForm):
    class Meta:
        model = RecurrenceRule
        fields = (
            "frequency",
            "interval",
            "weekdays",
            "start_date",
            "end_date",
            "exceptions",
        )

    def clean(self):
        cleaned = super().clean()
        frequency = cleaned.get("frequency")
        interval = cleaned.get("interval")
        weekdays = cleaned.get("weekdays")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")

        if interval is not None and interval < 1:
            self.add_error("interval", "Interval must be >= 1.")

        if frequency == RecurrenceRule.FREQ_WEEKLY and not weekdays:
            self.add_error("weekdays", "Weekdays are required.")

        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "End date cannot be before start date.")

        return cleaned
