import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from activities.models import Activity, ActivityCategory
from analytics.models import AggregatedDaily
from analytics.services import compute_daily, update_daily
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
        target_type="duration",
        target_value=60,
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
        date=dt.date(2026, 1, 2),
        start_time=dt.time(0, 0),
        end_time=dt.time(1, 0),
        timezone="Asia/Kathmandu",
        source="manual",
        is_recurring=False,
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
