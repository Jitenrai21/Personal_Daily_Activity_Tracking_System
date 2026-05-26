import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from activities.models import Activity, ActivityCategory
from analytics.models import AggregatedDaily
from analytics.services import compute_category_totals, compute_daily, compute_daily_intensity, update_daily
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
