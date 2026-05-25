import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from analytics.models import DailyScore


@pytest.mark.django_db
def test_scores_daily_api_returns_range(client):
    user = User.objects.create_user(username="api-score", password="Pass12345")
    client.login(username="api-score", password="Pass12345")

    DailyScore.objects.create(
        user=user,
        local_date=dt.date(2026, 4, 1),
        discipline_score=65,
        balance_score=70,
        recovery_score=80,
        composite_score=71.25,
    )

    response = client.get(
        reverse("scores_daily"),
        {"start": "2026-04-01", "end": "2026-04-02"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["start"] == "2026-04-01"
    assert payload["end"] == "2026-04-02"
    assert len(payload["items"]) == 2


@pytest.mark.django_db
def test_reflection_history_page_renders(client):
    user = User.objects.create_user(username="history-user", password="Pass12345")
    client.login(username="history-user", password="Pass12345")

    response = client.get(reverse("reflection_history"))
    assert response.status_code == 200
    assert "Reflection history" in response.content.decode("utf-8")
