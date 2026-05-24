import datetime as dt
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from analytics.models import AggregatedDaily
from planner.models import ScheduleBlock
from tracking.models import Session
from users.models import UserProfile

User = get_user_model()


def get_user_timezone(user):
    profile = UserProfile.objects.filter(user=user).first()
    tz_name = profile.timezone if profile else "UTC"
    return ZoneInfo(tz_name)


def get_day_bounds_utc(user, date):
    tz = get_user_timezone(user)
    local_start = dt.datetime.combine(date, dt.time.min, tzinfo=tz)
    local_end = local_start + dt.timedelta(days=1)
    return local_start.astimezone(dt.timezone.utc), local_end.astimezone(dt.timezone.utc)


def compute_daily(user, date):
    start_utc, end_utc = get_day_bounds_utc(user, date)

    sessions = (
        Session.objects.filter(
            user=user,
            end__isnull=False,
            start__lt=end_utc,
            end__gt=start_utc,
        )
        .select_related("activity")
        .order_by("start")
    )

    total_minutes = 0
    for session in sessions:
        overlap_start = max(session.start, start_utc)
        overlap_end = min(session.end, end_utc)
        seconds = max(0, (overlap_end - overlap_start).total_seconds())
        total_minutes += int(seconds // 60)

    blocks = ScheduleBlock.objects.filter(user=user, date=date)
    planned_minutes = 0
    for block in blocks:
        start_dt = dt.datetime.combine(date, block.start_time)
        end_dt = dt.datetime.combine(date, block.end_time)
        planned_minutes += int((end_dt - start_dt).total_seconds() // 60)

    completion_rate = None
    if planned_minutes > 0:
        completion_rate = total_minutes / planned_minutes

    return {
        "total_minutes": total_minutes,
        "planned_minutes": planned_minutes,
        "completion_rate": completion_rate,
        "sessions_count": sessions.count(),
    }


def update_daily(user, date):
    metrics = compute_daily(user, date)
    with transaction.atomic():
        record, _ = AggregatedDaily.objects.get_or_create(user=user, date=date)
        record.total_minutes = metrics["total_minutes"]
        record.planned_minutes = metrics["planned_minutes"]
        record.completion_rate = metrics["completion_rate"]
        record.sessions_count = metrics["sessions_count"]
        record.save()
    return record


def rebuild_last_days(days):
    if days < 1:
        return 0

    users = User.objects.all()
    total = 0
    for user in users:
        tz = get_user_timezone(user)
        local_today = timezone.now().astimezone(tz).date()
        for offset in range(days):
            date = local_today - dt.timedelta(days=offset)
            update_daily(user, date)
            total += 1
    return total
