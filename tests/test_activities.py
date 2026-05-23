import datetime as dt

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from activities.models import Activity, ActivityCategory, RecurrenceRule


@pytest.mark.django_db
def test_category_unique_per_user():
    user = User.objects.create_user(username="u1", password="Pass12345")
    ActivityCategory.objects.create(user=user, name="Health")
    with pytest.raises(IntegrityError):
        ActivityCategory.objects.create(user=user, name="Health")


@pytest.mark.django_db
def test_activity_crud_and_owner_scope(client):
    user1 = User.objects.create_user(username="u1", password="Pass12345")
    user2 = User.objects.create_user(username="u2", password="Pass12345")
    cat1 = ActivityCategory.objects.create(user=user1, name="Work")
    cat2 = ActivityCategory.objects.create(user=user2, name="Play")

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("activity_create"),
        {
            "title": "Study",
            "category": cat1.pk,
            "target_type": "duration",
            "target_value": 120,
            "priority": 2,
            "notes": "",
            "is_active": True,
        },
    )
    assert response.status_code == 302

    activity = Activity.objects.get(user=user1)
    detail_url = reverse("activity_detail", args=[activity.pk])

    client.logout()
    client.login(username="u2", password="Pass12345")
    response = client.get(detail_url)
    assert response.status_code == 404

    response = client.post(
        reverse("activity_create"),
        {
            "title": "Oops",
            "category": cat2.pk,
            "target_type": "duration",
            "target_value": 10,
            "priority": 1,
            "notes": "",
            "is_active": True,
        },
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_recurrence_validation():
    user = User.objects.create_user(username="u1", password="Pass12345")
    cat = ActivityCategory.objects.create(user=user, name="Work")
    activity = Activity.objects.create(
        user=user,
        title="Study",
        category=cat,
        target_type="duration",
        target_value=60,
        priority=1,
    )

    rule = RecurrenceRule(
        activity=activity,
        frequency="weekly",
        interval=1,
        weekdays=None,
        start_date=dt.date(2026, 1, 1),
        end_date=dt.date(2026, 1, 31),
    )

    with pytest.raises(Exception):
        rule.full_clean()


@pytest.mark.django_db
def test_toggle_activity_htmx(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    cat = ActivityCategory.objects.create(user=user, name="Health")
    activity = Activity.objects.create(
        user=user,
        title="Run",
        category=cat,
        target_type="count",
        target_value=3,
        priority=2,
    )

    client.login(username="u1", password="Pass12345")
    response = client.post(
        reverse("activity_toggle", args=[activity.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    activity.refresh_from_db()
    assert activity.is_active is False
