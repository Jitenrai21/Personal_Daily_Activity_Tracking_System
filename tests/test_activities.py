import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from activities.models import Activity, ActivityCategory


@pytest.mark.django_db
def test_category_unique_per_user():
    user = User.objects.create_user(username="u1", password="Pass12345")
    ActivityCategory.objects.create(user=user, name="Health")
    with pytest.raises(IntegrityError):
        ActivityCategory.objects.create(user=user, name="Health")


@pytest.mark.django_db
def test_planner_category_crud_and_scope(client):
    user1 = User.objects.create_user(username="u1", password="Pass12345")
    user2 = User.objects.create_user(username="u2", password="Pass12345")

    client.login(username="u1", password="Pass12345")
    response = client.post(reverse("planner_category_create"), {"name": "Work"})
    assert response.status_code == 302

    category = ActivityCategory.objects.get(user=user1, name="Work")

    update = client.post(
        reverse("planner_category_update", args=[category.pk]),
        {"name": "Focus", "description": "Deep work"},
    )
    assert update.status_code == 302
    category.refresh_from_db()
    assert category.name == "Focus"

    client.logout()
    client.login(username="u2", password="Pass12345")
    forbidden = client.post(
        reverse("planner_category_update", args=[category.pk]),
        {"name": "Hijack"},
    )
    assert forbidden.status_code == 404

    own = ActivityCategory.objects.create(user=user2, name="Play")
    delete = client.post(reverse("planner_category_delete", args=[own.pk]))
    assert delete.status_code == 302
    assert not ActivityCategory.objects.filter(pk=own.pk).exists()


@pytest.mark.django_db
def test_planner_activity_crud_and_scope(client):
    user = User.objects.create_user(username="u1", password="Pass12345")
    other = User.objects.create_user(username="u2", password="Pass12345")
    cat = ActivityCategory.objects.create(user=user, name="Health")

    client.login(username="u1", password="Pass12345")
    create = client.post(
        reverse("planner_activity_create"),
        {
            "title": "Run",
            "category": cat.pk,
            "priority": 2,
            "notes": "Morning",
        },
    )
    assert create.status_code == 302

    activity = Activity.objects.get(user=user, title="Run")

    update = client.post(
        reverse("planner_activity_update", args=[activity.pk]),
        {
            "title": "Run fast",
            "category": cat.pk,
            "priority": 1,
            "notes": "Track pace",
        },
    )
    assert update.status_code == 302
    activity.refresh_from_db()
    assert activity.title == "Run fast"

    client.logout()
    client.login(username="u2", password="Pass12345")
    response = client.post(
        reverse("planner_activity_update", args=[activity.pk]),
        {
            "title": "Steal",
            "category": cat.pk,
            "priority": 1,
            "notes": "",
        },
    )
    assert response.status_code == 404

    own_cat = ActivityCategory.objects.create(user=other, name="Play")
    own_activity = Activity.objects.create(
        user=other,
        title="Game",
        category=own_cat,
        priority=3,
    )
    delete = client.post(reverse("planner_activity_delete", args=[own_activity.pk]))
    assert delete.status_code == 302
    assert not Activity.objects.filter(pk=own_activity.pk).exists()
