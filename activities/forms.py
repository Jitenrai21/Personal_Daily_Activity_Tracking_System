from django import forms
from django.core.exceptions import ValidationError

from activities.models import Activity, ActivityCategory, RecurrenceRule


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ActivityCategory
        fields = ("name", "color", "description", "is_default", "is_archived")


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = (
            "title",
            "category",
            "target_type",
            "target_value",
            "priority",
            "notes",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["category"].queryset = ActivityCategory.objects.filter(
                user=user, is_archived=False
            )

    def clean_target_value(self):
        value = self.cleaned_data.get("target_value")
        if value is None or value <= 0:
            raise ValidationError("Target value must be greater than 0.")
        return value


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
