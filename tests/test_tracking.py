import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityCategory
from tracking.forms import SessionLogForm
from tracking.models import Session


@pytest.mark.django_db
def test_session_duration_minutes():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Focus")
    activity = Activity.objects.create(
        user=user,
        title="Deep work",
        category=category,
        priority=1,
    )
    start = timezone.now()
    end = start + dt.timedelta(minutes=45)
    session = Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=start.date(),
        start_time=start.time().replace(microsecond=0),
        end_time=end.time().replace(microsecond=0),
        start=start,
        end=end,
        source=Session.SOURCE_MANUAL,
    )
    assert session.duration_minutes == 45


@pytest.mark.django_db
def test_session_duration_minutes_respects_pause_time():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Focus")
    activity = Activity.objects.create(
        user=user,
        title="Deep work",
        category=category,
        priority=1,
    )
    start = timezone.now()
    end = start + dt.timedelta(minutes=45)
    session = Session.objects.create(
        user=user,
        activity=activity,
        category=category,
        local_date=start.date(),
        start_time=start.time().replace(microsecond=0),
        end_time=end.time().replace(microsecond=0),
        start=start,
        end=end,
        paused_seconds=900,
        source=Session.SOURCE_MANUAL,
    )
    assert session.duration_minutes == 30


@pytest.mark.django_db
def test_start_stop_timer_flow(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Health")
    activity = Activity.objects.create(
        user=user,
        title="Stretch",
        category=category,
        priority=1,
    )

    client.login(username="u1", password="Pass12345")
    start_response = client.post(
        reverse("session_start"),
        {"activity_id": activity.pk, "target_id": "session-toggle"},
        HTTP_HX_REQUEST="true",
    )
    assert start_response.status_code == 200
    session = Session.objects.get(user=user, end__isnull=True)
    assert session.activity == activity

    stop_response = client.post(
        reverse("session_stop"),
        {"target_id": "session-toggle"},
        HTTP_HX_REQUEST="true",
    )
    assert stop_response.status_code == 200
    session.refresh_from_db()
    assert session.end is not None


@pytest.mark.django_db
def test_manual_session_log(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Study")
    activity = Activity.objects.create(
        user=user,
        title="Read",
        category=category,
        priority=2,
    )

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("session_log"),
        {
            "category": category.pk,
            "activity": activity.pk,
            "local_date": "2026-01-01",
            "start_time": "09:00",
            "end_time": "09:30",
            "notes": "Morning reading",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, source=Session.SOURCE_MANUAL).count() == 1


@pytest.mark.django_db
def test_duration_only_session_log(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Study")
    activity = Activity.objects.create(
        user=user,
        title="Read",
        category=category,
        priority=2,
    )

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("session_log"),
        {
            "category": category.pk,
            "activity": activity.pk,
            "local_date": "2026-01-02",
            "duration_minutes": 25,
            "notes": "Quick session",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    session = Session.objects.get(user=user, source=Session.SOURCE_MANUAL)
    assert session.duration_minutes == 25
    assert session.start is None


@pytest.mark.django_db
def test_end_before_start_rejected(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Study")
    activity = Activity.objects.create(
        user=user,
        title="Read",
        category=category,
        priority=2,
    )

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("session_log"),
        {
            "activity": activity.pk,
            "local_date": "2026-01-03",
            "start_time": "10:00",
            "end_time": "09:00",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, source=Session.SOURCE_MANUAL).count() == 0


@pytest.mark.django_db
def test_single_active_session_guard(client):
    User.objects.create_user(username="u1", password="Pass12345")

    client.login(username="u1", password="Pass12345")
    first = client.post(
        reverse("session_start"),
        {"target_id": "session-toggle"},
        HTTP_HX_REQUEST="true",
    )
    assert first.status_code == 200

    second = client.post(
        reverse("session_start"),
        {"target_id": "session-toggle"},
        HTTP_HX_REQUEST="true",
    )
    assert second.status_code == 409


@pytest.mark.django_db
def test_session_user_isolation(client):
    user1 = User.objects.create_user(username="u1", password="Pass12345")

    session = Session.objects.create(
        user=user1,
        local_date=timezone.now().date(),
        start=timezone.now(),
        end=timezone.now() + dt.timedelta(minutes=5),
        source=Session.SOURCE_MANUAL,
    )

    client.login(username="u2", password="Pass12345")
    response = client.get(reverse("session_detail", args=[session.pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_category_queryset_scoped_to_user():
    user = User.objects.create_user(username="u1", password="Pass12345")
    other = User.objects.create_user(username="u2", password="Pass12345")
    own = ActivityCategory.objects.create(user=user, name="Own")
    ActivityCategory.objects.create(user=other, name="Other")

    form = SessionLogForm(user=user)
    categories = list(form.fields["category"].queryset)
    assert own in categories
    assert all(item.user_id == user.id for item in categories)
