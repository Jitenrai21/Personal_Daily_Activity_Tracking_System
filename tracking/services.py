import datetime as dt

from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from activities.models import Activity
from tracking.models import Session
from users.models import UserProfile


TIMER_STATE_KEY = "timer_state"
PAUSED_AT_KEY = "paused_at"
TIMER_RUNNING = "running"
TIMER_PAUSED = "paused"


def _timer_metadata(metadata=None, *, state=TIMER_RUNNING, paused_at=None):
    payload = dict(metadata or {})
    payload[TIMER_STATE_KEY] = state
    if paused_at is None:
        payload.pop(PAUSED_AT_KEY, None)
    else:
        payload[PAUSED_AT_KEY] = paused_at.isoformat()
    return payload


def _parse_paused_at(session):
    metadata = session.metadata if isinstance(session.metadata, dict) else {}
    paused_at = metadata.get(PAUSED_AT_KEY)
    if not paused_at:
        return None
    try:
        return dt.datetime.fromisoformat(paused_at)
    except ValueError:
        return None


def _get_active_timer_session(user):
    return (
        Session.objects.select_for_update()
        .filter(user=user, end__isnull=True, source=Session.SOURCE_TIMER)
        .first()
    )


def get_user_timezone(user):
    profile = UserProfile.objects.filter(user=user).first()
    tz_name = profile.timezone if profile else "UTC"
    return ZoneInfo(tz_name)


def start_timer_session(user, activity=None, notes="", metadata=None):
    with transaction.atomic():
        running = _get_active_timer_session(user)
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
            paused_seconds=0,
            source=Session.SOURCE_TIMER,
            notes=notes,
            metadata=_timer_metadata(metadata, state=TIMER_RUNNING),
        )
        session.full_clean()
        session.save()

    return session, None


def pause_timer_session(user):
    with transaction.atomic():
        session = _get_active_timer_session(user)
        if not session:
            return None

        if session.timer_state == TIMER_PAUSED:
            return session

        now = timezone.now()
        session.metadata = _timer_metadata(session.metadata, state=TIMER_PAUSED, paused_at=now)
        session.full_clean()
        session.save(update_fields=["metadata", "updated_at"])

    return session


def resume_timer_session(user):
    with transaction.atomic():
        session = _get_active_timer_session(user)
        if not session:
            return None

        if session.timer_state != TIMER_PAUSED:
            return session

        paused_at = _parse_paused_at(session)
        now = timezone.now()
        if paused_at:
            session.paused_seconds = (session.paused_seconds or 0) + max(
                0, int((now - paused_at).total_seconds())
            )
        session.metadata = _timer_metadata(session.metadata, state=TIMER_RUNNING)
        session.full_clean()
        session.save(update_fields=["paused_seconds", "metadata", "updated_at"])

    return session


def stop_timer_session(user):
    with transaction.atomic():
        running = _get_active_timer_session(user)
        if not running:
            return None

        now = timezone.now()
        local_now = now.astimezone(get_user_timezone(user))
        paused_at = _parse_paused_at(running)
        if paused_at:
            running.paused_seconds = (running.paused_seconds or 0) + max(
                0, int((now - paused_at).total_seconds())
            )
        running.metadata = _timer_metadata(running.metadata, state="stopped")
        running.end = now
        running.end_time = local_now.time().replace(microsecond=0)
        running.full_clean()
        running.save(
            update_fields=[
                "end",
                "end_time",
                "duration_minutes",
                "paused_seconds",
                "metadata",
                "updated_at",
            ]
        )

    return running
