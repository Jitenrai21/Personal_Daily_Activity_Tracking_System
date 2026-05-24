import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_view_requires_login(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_dashboard_view_renders_for_user(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    client.login(username="u1", password="Pass12345")
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert "Your momentum snapshot" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_dashboard_api_endpoints(client):
    user = User.objects.create_user(username="u2", password="Pass12345")
    client.login(username="u2", password="Pass12345")

    daily = client.get(reverse("metrics_daily"))
    weekly = client.get(reverse("metrics_weekly"))
    monthly = client.get(reverse("metrics_monthly"))
    heatmap = client.get(reverse("metrics_heatmap"))

    assert daily.status_code == 200
    assert weekly.status_code == 200
    assert monthly.status_code == 200
    assert heatmap.status_code == 200

    assert "labels" in daily.json()
    assert "weeks" in heatmap.json()
