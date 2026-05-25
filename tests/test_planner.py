import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from activities.models import Activity, ActivityCategory
from planner.forms import ScheduleBlockForm
from planner.models import ScheduleBlock
from tracking.models import Session


@pytest.mark.django_db
def test_planner_auto_duration_from_times():
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

    form = ScheduleBlockForm(
        {
            "activity": activity.pk,
            "category": category.pk,
            "date": "2026-01-01",
            "start_time": "09:00",
            "end_time": "10:00",
        },
        user=user,
    )
    assert form.is_valid()
    block = form.save(commit=False)
    block.user = user
    block.save()
    assert block.duration_minutes == 60


@pytest.mark.django_db
def test_planner_duration_only_block():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Health")
    activity = Activity.objects.create(
        user=user,
        title="Stretch",
        category=category,
        target_type="duration",
        target_value=10,
        priority=1,
    )

    form = ScheduleBlockForm(
        {
            "activity": activity.pk,
            "category": category.pk,
            "date": "2026-01-02",
            "duration_minutes": 25,
        },
        user=user,
    )
    assert form.is_valid()
    block = form.save(commit=False)
    block.user = user
    block.save()
    assert block.duration_minutes == 25


@pytest.mark.django_db
def test_planner_end_before_start_rejected():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Focus")
    activity = Activity.objects.create(
        user=user,
        title="Read",
        category=category,
        target_type="duration",
        target_value=30,
        priority=1,
    )

    form = ScheduleBlockForm(
        {
            "activity": activity.pk,
            "category": category.pk,
            "date": "2026-01-03",
            "start_time": "10:00",
            "end_time": "09:00",
        },
        user=user,
    )
    assert not form.is_valid()


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
        category=category1,
        date=dt.date(2026, 1, 1),
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
    )

    client.login(username="u2", password="Pass12345")
    response = client.get(reverse("planner_day"))
    assert response.status_code == 200
    assert "Task" not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_planner_archived_category_excluded_from_form():
    user = User.objects.create_user(username="u1", password="Pass12345")
    active = ActivityCategory.objects.create(user=user, name="Active")
    archived = ActivityCategory.objects.create(
        user=user, name="Archived", is_archived=True
    )

    form = ScheduleBlockForm(user=user)
    categories = list(form.fields["category"].queryset)
    assert active in categories
    assert archived not in categories


@pytest.mark.django_db
def test_planner_start_timer_creates_session(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
        target_type="duration",
        target_value=30,
        priority=1,
    )
    block = ScheduleBlock.objects.create(
        user=user,
        activity=activity,
        category=category,
        date=dt.date(2026, 1, 4),
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
    )

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("schedule_start_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, end__isnull=True).count() == 1


@pytest.mark.django_db
def test_planner_stop_timer_restores_start_ui(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
        target_type="duration",
        target_value=30,
        priority=1,
    )
    block = ScheduleBlock.objects.create(
        user=user,
        activity=activity,
        category=category,
        date=dt.date(2026, 1, 4),
        start_time=dt.time(9, 0),
        end_time=dt.time(10, 0),
    )

    client.login(username="u1", password="Pass12345")
    client.post(reverse("schedule_start_timer", args=[block.pk]), HTTP_HX_REQUEST="true")

    response = client.post(
        reverse("schedule_stop_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, end__isnull=True).count() == 0
    assert "Start timer" in response.content.decode("utf-8")
