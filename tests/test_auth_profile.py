import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from users.models import UserProfile


@pytest.mark.django_db
def test_signup_creates_user_and_profile(client):
    response = client.post(
        reverse("signup"),
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "StrongPass123",
            "password2": "StrongPass123",
        },
    )
    assert response.status_code == 302
    user = User.objects.get(username="newuser")
    assert UserProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_and_profile_update(client):
    user = User.objects.create_user(
        username="tester",
        email="tester@example.com",
        password="StrongPass123",
    )
    client.login(username="tester", password="StrongPass123")
    response = client.post(
        reverse("profile"),
        {
            "timezone": "UTC",
            "wake_time": "07:00",
            "sleep_time": "22:30",
            "sleep_target_minutes": 450,
            "daily_focus_minutes": 120,
            "weekly_goal_minutes": 600,
        },
    )
    assert response.status_code == 302
    user.refresh_from_db()
    profile = user.userprofile
    assert profile.sleep_target_minutes == 450
    assert profile.weekly_goal_minutes == 600


@pytest.mark.django_db
def test_password_reset_flow_sends_email(client):
    User.objects.create_user(
        username="resetuser",
        email="reset@example.com",
        password="StrongPass123",
    )
    response = client.post(
        reverse("password_reset"),
        {"email": "reset@example.com"},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_profile_requires_login(client):
    response = client.get(reverse("profile"))
    assert response.status_code == 302
    assert reverse("login") in response.url
