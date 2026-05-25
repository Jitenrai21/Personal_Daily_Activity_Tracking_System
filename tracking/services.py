from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from activities.models import Activity
from tracking.models import Session
from users.models import UserProfile


def get_user_timezone(user):
    profile = UserProfile.objects.filter(user=user).first()
    tz_name = profile.timezone if profile else "UTC"
    return ZoneInfo(tz_name)


def start_timer_session(user, activity=None, notes="", metadata=None):
    with transaction.atomic():
        running = (
            Session.objects.select_for_update()
            .filter(user=user, end__isnull=True)
            .first()
        )
        if running:
            return None, running

        now = timezone.now()
        local_now = now.astimezone(get_user_timezone(user))
        session = Session(
            user=user,
            activity=activity,
            category=activity.category if isinstance(activity, Activity) else None,
            local_date=local_now.date(),
            start_time=local_now.time().replace(microsecond=0),
            start=now,
            source=Session.SOURCE_TIMER,
            notes=notes,
            metadata=metadata or None,
        )
        session.full_clean()
        session.save()

    return session, None


def stop_timer_session(user):
    with transaction.atomic():
        running = (
            Session.objects.select_for_update()
            .filter(user=user, end__isnull=True)
            .first()
        )
        if not running:
            return None

        now = timezone.now()
        local_now = now.astimezone(get_user_timezone(user))
        running.end = now
        running.end_time = local_now.time().replace(microsecond=0)
        running.full_clean()
        running.save(update_fields=["end", "end_time", "duration_minutes", "updated_at"])

    return running
