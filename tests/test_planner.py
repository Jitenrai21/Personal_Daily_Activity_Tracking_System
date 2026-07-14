import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

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
    User.objects.create_user(username="u2", password="Pass12345")
    category1 = ActivityCategory.objects.create(user=user1, name="Work")

    activity1 = Activity.objects.create(
        user=user1,
        title="Task",
        category=category1,
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
def test_planner_category_queryset_scoped_to_user():
    user = User.objects.create_user(username="u1", password="Pass12345")
    other = User.objects.create_user(username="u2", password="Pass12345")
    own = ActivityCategory.objects.create(user=user, name="Own")
    ActivityCategory.objects.create(user=other, name="Other")

    form = ScheduleBlockForm(user=user)
    categories = list(form.fields["category"].queryset)
    assert own in categories
    assert all(item.user_id == user.id for item in categories)


@pytest.mark.django_db
def test_planner_start_timer_creates_session(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
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
    session = Session.objects.get(user=user, end__isnull=True)
    assert session.paused_seconds == 0


@pytest.mark.django_db
def test_planner_pause_resume_timer_flow(client, monkeypatch):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
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

    start_time = timezone.make_aware(dt.datetime(2026, 1, 4, 9, 0), dt.timezone.utc)
    pause_time = timezone.make_aware(dt.datetime(2026, 1, 4, 9, 15), dt.timezone.utc)
    resume_time = timezone.make_aware(dt.datetime(2026, 1, 4, 9, 25), dt.timezone.utc)
    stop_time = timezone.make_aware(dt.datetime(2026, 1, 4, 9, 55), dt.timezone.utc)

    client.login(username="u1", password="Pass12345")
    monkeypatch.setattr("tracking.services.timezone.now", lambda: start_time)
    start_response = client.post(
        reverse("schedule_start_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert start_response.status_code == 200

    monkeypatch.setattr("tracking.services.timezone.now", lambda: pause_time)
    pause_response = client.post(
        reverse("schedule_pause_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert pause_response.status_code == 200
    session = Session.objects.get(user=user, end__isnull=True)
    assert session.is_paused
    assert session.paused_at is not None

    monkeypatch.setattr("tracking.services.timezone.now", lambda: resume_time)
    resume_response = client.post(
        reverse("schedule_resume_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert resume_response.status_code == 200
    session.refresh_from_db()
    assert session.paused_seconds == 600
    assert session.is_running

    monkeypatch.setattr("tracking.services.timezone.now", lambda: stop_time)
    stop_response = client.post(
        reverse("schedule_stop_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert stop_response.status_code == 200
    session.refresh_from_db()
    assert session.end is not None
    assert session.duration_minutes == 45


@pytest.mark.django_db
def test_planner_stop_timer_restores_start_ui(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Build",
        category=category,
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
    client.post(
        reverse("schedule_start_timer", args=[block.pk]), HTTP_HX_REQUEST="true"
    )

    response = client.post(
        reverse("schedule_stop_timer", args=[block.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, end__isnull=True).count() == 0
