import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from activities.models import Activity, ActivityCategory
from planner.models import ScheduleBlock, WeeklyRoutine
from planner.services import generate_blocks_for_date


@pytest.mark.django_db
def test_schedule_block_overlap_rejected():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Study",
        category=category,
        target_type="duration",
        target_value=60,
        priority=1,
    )

    ScheduleBlock.objects.create(
        user=user,
        activity=activity,
        date=dt.date(2026, 1, 1),
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
        timezone="Asia/Kathmandu",
        source=ScheduleBlock.SOURCE_MANUAL,
        is_recurring=False,
    )

    block = ScheduleBlock(
        user=user,
        activity=activity,
        date=dt.date(2026, 1, 1),
        start_time=dt.time(9, 30),
        end_time=dt.time(10, 30),
        timezone="Asia/Kathmandu",
        source=ScheduleBlock.SOURCE_MANUAL,
        is_recurring=False,
    )

    with pytest.raises(Exception):
        block.full_clean()


@pytest.mark.django_db
def test_generate_from_routine():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Health")
    activity = Activity.objects.create(
        user=user,
        title="Run",
        category=category,
        target_type="count",
        target_value=3,
        priority=1,
    )

    WeeklyRoutine.objects.create(
        user=user,
        activity=activity,
        weekday=0,
        start_time=dt.time(7, 0),
        end_time=dt.time(7, 30),
        timezone="Asia/Kathmandu",
    )

    date = dt.date(2026, 1, 5)  # Monday
    created = generate_blocks_for_date(user, date)
    assert len(created) == 1
    assert ScheduleBlock.objects.filter(user=user, date=date).count() == 1


@pytest.mark.django_db
def test_schedule_user_isolation(client):
    user1 = User.objects.create_user(username="u1", password="Pass12345")
    user2 = User.objects.create_user(username="u2", password="Pass12345")
    category1 = ActivityCategory.objects.create(user=user1, name="Work")
    category2 = ActivityCategory.objects.create(user=user2, name="Play")

    activity1 = Activity.objects.create(
        user=user1,
        title="Task",
        category=category1,
        target_type="duration",
        target_value=30,
        priority=1,
    )

    ScheduleBlock.objects.create(
        user=user1,
        activity=activity1,
        date=dt.date(2026, 1, 1),
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
        timezone="Asia/Kathmandu",
        source=ScheduleBlock.SOURCE_MANUAL,
        is_recurring=False,
    )

    client.login(username="u2", password="Pass12345")
    response = client.get(reverse("planner_day"))
    assert response.status_code == 200
    assert "Task" not in response.content.decode("utf-8")
