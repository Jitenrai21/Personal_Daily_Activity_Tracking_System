from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from users.models import UserProfile


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = (
            "timezone",
            "wake_time",
            "sleep_time",
            "sleep_target_minutes",
            "daily_focus_minutes",
            "weekly_goal_minutes",
        )
        widgets = {
            "wake_time": forms.TimeInput(attrs={"type": "time"}),
            "sleep_time": forms.TimeInput(attrs={"type": "time"}),
        }
