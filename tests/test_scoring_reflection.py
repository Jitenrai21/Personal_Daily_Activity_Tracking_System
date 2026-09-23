import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from activities.models import Activity, ActivityCategory
from analytics.models import DailyReflection, DailyScore
from analytics.scoring import compute_daily_score, upsert_daily_score
from planner.models import ScheduleBlock
from tracking.models import Session
from users.models import UserProfile


@pytest.mark.django_db
def test_daily_score_is_normalized_and_persisted():
    user = User.objects.create_user(username="score-user", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.daily_focus_minutes = 120
    profile.sleep_target_minutes = 480
    profile.save()

    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
        weight=1,
    )

    local_date = dt.date(2026, 1, 10)
    start = dt.datetime(2026, 1, 10, 9, 0, tzinfo=dt.timezone.utc)
    end = dt.datetime(2026, 1, 10, 10, 0, tzinfo=dt.timezone.utc)

    Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=local_date,
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
        start=start,
        end=end,
        source="manual",
    )
    ScheduleBlock.objects.create(
        user=user,
        activity=activity,
        category=category,
        date=local_date,
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
    )

    metrics = compute_daily_score(user, local_date)
    assert 0 <= metrics["discipline_score"] <= 100
    assert 0 <= metrics["balance_score"] <= 100
    assert 0 <= metrics["recovery_score"] <= 100
    assert 0 <= metrics["composite_score"] <= 100

    score = upsert_daily_score(user, local_date)
    assert DailyScore.objects.filter(user=user, local_date=local_date).count() == 1
    assert score.composite_score == metrics["composite_score"]


@pytest.mark.django_db
def test_scoring_idempotent_for_same_data():
    user = User.objects.create_user(username="idem-user", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])

    local_date = dt.date(2026, 2, 1)
    score1 = upsert_daily_score(user, local_date)
    score2 = upsert_daily_score(user, local_date)

    assert DailyScore.objects.filter(user=user, local_date=local_date).count() == 1
    assert score1.composite_score == score2.composite_score


@pytest.mark.django_db
def test_reflection_create_update_history_api(client):
    user = User.objects.create_user(username="reflect-user", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])

    client.login(username="reflect-user", password="Pass12345")

    local_date = "2026-03-01"
    detail = client.get(reverse("scores_detail", args=[local_date]))
    assert detail.status_code == 200

    create = client.post(
        reverse("reflections_create"),
        {
            "local_date": local_date,
            "answer_text": "I stayed focused after lunch.",
            "mood": "good",
            "tags": '["focus", "routine"]',
        },
    )
    assert create.status_code == 200
    reflection_id = create.json()["id"]

    patch = client.patch(
        reverse("reflections_update", args=[reflection_id]),
        data='{"answer_text":"Updated reflection","mood":"great"}',
        content_type="application/json",
    )
    assert patch.status_code == 200
    assert patch.json()["mood"] == "great"

    history = client.get(
        reverse("reflections_history"),
        {"start": local_date, "end": local_date},
    )
    assert history.status_code == 200
    assert len(history.json()["items"]) >= 1

    assert (
        DailyReflection.objects.filter(
            user=user,
            local_date=dt.date.fromisoformat(local_date),
        ).count()
        == 1
    )
