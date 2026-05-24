import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, ActivityCategory
from tracking.models import Session


@pytest.mark.django_db
def test_session_duration_minutes():
    user = User.objects.create_user(username="u1", password="Pass12345")
    category = ActivityCategory.objects.create(user=user, name="Focus")
    activity = Activity.objects.create(
        user=user,
        title="Deep work",
        category=category,
        target_type="duration",
        target_value=60,
        priority=1,
    )
    start = timezone.now()
    end = start + dt.timedelta(minutes=45)
    session = Session.objects.create(
        user=user,
        activity=activity,
        start=start,
        end=end,
        source=Session.SOURCE_MANUAL,
    )
    assert session.duration_minutes == 45


@pytest.mark.django_db
def test_start_stop_timer_flow(client):
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
        target_type="duration",
        target_value=30,
        priority=2,
    )

    client.login(username="u1", password="Pass12345")
    start = dt.datetime(2026, 1, 1, 9, 0)
    end = dt.datetime(2026, 1, 1, 9, 30)
    response = client.post(
        reverse("session_log"),
        {
            "activity": activity.pk,
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
            "notes": "Morning reading",
        },
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert Session.objects.filter(user=user, source=Session.SOURCE_MANUAL).count() == 1


@pytest.mark.django_db
def test_single_active_session_guard(client):
    user = User.objects.create_user(username="u1", password="Pass12345")

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
    user2 = User.objects.create_user(username="u2", password="Pass12345")

    session = Session.objects.create(
        user=user1,
        start=timezone.now(),
        end=timezone.now() + dt.timedelta(minutes=5),
        source=Session.SOURCE_MANUAL,
    )

    client.login(username="u2", password="Pass12345")
    response = client.get(reverse("session_detail", args=[session.pk]))
    assert response.status_code == 404
