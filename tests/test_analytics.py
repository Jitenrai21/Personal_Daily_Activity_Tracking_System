import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityCategory
from analytics import views as analytics_views
from analytics.models import AggregatedDaily
from analytics.services import (
    compute_category_totals,
    compute_daily,
    compute_daily_intensity,
    update_daily,
)
from planner.models import ScheduleBlock
from tracking.models import Session
from users.models import UserProfile


@pytest.mark.django_db
def test_compute_daily_splits_midnight_session():
    user = User.objects.create_user(username="u1", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "Asia/Kathmandu"
    profile.save(update_fields=["timezone"])
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Late shift",
        category=category,
        priority=1,
    )

    tz = ZoneInfo("Asia/Kathmandu")
    local_start = dt.datetime(2026, 1, 1, 23, 30, tzinfo=tz)
    local_end = dt.datetime(2026, 1, 2, 0, 30, tzinfo=tz)

    Session.objects.create(
        user=user,
        local_date=local_start.date(),
        start=local_start.astimezone(dt.timezone.utc),
        end=local_end.astimezone(dt.timezone.utc),
        source=Session.SOURCE_MANUAL,
    )

    ScheduleBlock.objects.create(
        user=user,
        activity=activity,
        category=category,
        date=dt.date(2026, 1, 2),
        start_time=dt.time(0, 0),
        end_time=dt.time(1, 0),
    )

    metrics = compute_daily(user, dt.date(2026, 1, 2))
    assert metrics["total_minutes"] == 30
    assert metrics["planned_minutes"] == 60
    assert metrics["completion_rate"] == pytest.approx(0.5)


@pytest.mark.django_db
def test_update_daily_creates_record():
    user = User.objects.create_user(username="u2", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])

    start = timezone.now()
    end = start + dt.timedelta(minutes=20)
    Session.objects.create(
        user=user,
        local_date=start.date(),
        start=start,
        end=end,
        source=Session.SOURCE_MANUAL,
    )

    record = update_daily(user, start.date())
    assert AggregatedDaily.objects.filter(user=user, date=start.date()).exists()
    assert record.total_minutes >= 20


@pytest.mark.django_db
def test_category_totals_weighted_by_priority():
    user = User.objects.create_user(username="u3", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Deep")
    low_category = ActivityCategory.objects.create(user=user, name="Light")
    high = Activity.objects.create(
        user=user,
        title="Deep work",
        category=category,
        priority=3,
    )
    low = Activity.objects.create(
        user=user,
        title="Email",
        category=low_category,
        priority=1,
    )

    start = timezone.now()
    Session.objects.create(
        user=user,
        activity=high,
        category=category,
        local_date=start.date(),
        start=start,
        end=start + dt.timedelta(minutes=10),
        source=Session.SOURCE_MANUAL,
    )
    Session.objects.create(
        user=user,
        activity=low,
        category=low_category,
        local_date=start.date(),
        start=start,
        end=start + dt.timedelta(minutes=10),
        source=Session.SOURCE_MANUAL,
    )

    totals = compute_category_totals(user, start.date(), start.date())
    totals_map = {row["name"]: row for row in totals}
    assert totals_map["Deep"]["intensity_score"] == 30
    assert totals_map["Light"]["intensity_score"] == 10


@pytest.mark.django_db
def test_daily_intensity_uses_priority():
    user = User.objects.create_user(username="u4", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Focus")
    activity = Activity.objects.create(
        user=user,
        title="Study",
        category=category,
        priority=2,
    )
    start = timezone.now()
    Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=start.date(),
        start=start,
        end=start + dt.timedelta(minutes=15),
        source=Session.SOURCE_MANUAL,
    )

    intensity = compute_daily_intensity(user, start.date())
    assert intensity == 30


@pytest.mark.django_db
def test_dashboard_defaults_to_current_window(monkeypatch, client):
    user = User.objects.create_user(username="u5", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])

    fixed_now = dt.datetime(2026, 6, 2, 12, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(analytics_views.timezone, "now", lambda: fixed_now)

    AggregatedDaily.objects.create(
        user=user,
        date=dt.date(2026, 5, 31),
        total_minutes=45,
        planned_minutes=30,
        completion_rate=1.5,
        sessions_count=1,
    )
    AggregatedDaily.objects.create(
        user=user,
        date=dt.date(2026, 6, 1),
        total_minutes=60,
        planned_minutes=60,
        completion_rate=1.0,
        sessions_count=1,
    )

    client.force_login(user)
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert response.context["range_days"] == 30
    assert response.context["daily_labels"][0] == "2026-05-04"
    assert response.context["daily_labels"][-1] == "2026-06-02"
    assert response.context["from_date_value"] == "2026-05-04"
    assert response.context["to_date_value"] == "2026-06-02"
    assert response.context["kpis"]["total_actual"] == 105


@pytest.mark.django_db
def test_dashboard_filters_by_from_and_to_dates(monkeypatch, client):
    user = User.objects.create_user(username="u6", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user, title="Focus", category=category, priority=2
    )

    fixed_now = dt.datetime(2026, 6, 2, 12, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(analytics_views.timezone, "now", lambda: fixed_now)

    AggregatedDaily.objects.create(
        user=user,
        date=dt.date(2026, 5, 30),
        total_minutes=20,
        planned_minutes=10,
        completion_rate=2.0,
        sessions_count=1,
    )
    AggregatedDaily.objects.create(
        user=user,
        date=dt.date(2026, 5, 31),
        total_minutes=40,
        planned_minutes=20,
        completion_rate=2.0,
        sessions_count=1,
    )

    start = dt.datetime(2026, 5, 30, 9, 0, tzinfo=dt.timezone.utc)
    Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=dt.date(2026, 5, 30),
        start=start,
        end=start + dt.timedelta(minutes=20),
        source=Session.SOURCE_MANUAL,
    )
    Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=dt.date(2026, 5, 31),
        start=start + dt.timedelta(days=1),
        end=start + dt.timedelta(days=1, minutes=40),
        source=Session.SOURCE_MANUAL,
    )

    client.force_login(user)
    response = client.get(
        reverse("dashboard"),
        {"from_date": "2026-05-30", "to_date": "2026-05-31"},
    )

    assert response.status_code == 200
    assert response.context["range_days"] == 2
    assert response.context["daily_labels"] == ["2026-05-30", "2026-05-31"]
    assert response.context["kpis"]["total_actual"] == 60
    assert response.context["from_date_value"] == "2026-05-30"
    assert response.context["to_date_value"] == "2026-05-31"
    assert response.context["category_daily_series"][0]["labels"] == [
        "2026-05-30",
        "2026-05-31",
    ]


@pytest.mark.django_db
def test_dashboard_single_boundary_filters(monkeypatch, client):
    user = User.objects.create_user(username="u7", password="Pass12345")
    profile = UserProfile.objects.get(user=user)
    profile.timezone = "UTC"
    profile.save(update_fields=["timezone"])

    fixed_now = dt.datetime(2026, 6, 2, 12, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(analytics_views.timezone, "now", lambda: fixed_now)

    client.force_login(user)
    response = client.get(reverse("dashboard"), {"from_date": "2026-05-30"})

    assert response.status_code == 200
    assert response.context["daily_labels"][0] == "2026-05-30"
    assert response.context["daily_labels"][-1] == "2026-06-02"
    assert response.context["from_date_value"] == "2026-05-30"
    assert response.context["to_date_value"] == "2026-06-02"
