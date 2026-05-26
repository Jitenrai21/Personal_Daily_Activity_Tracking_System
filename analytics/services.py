import datetime as dt
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from analytics.models import AggregatedDaily
from activities.models import ActivityCategory
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

    duration_only_sessions = Session.objects.filter(
        user=user,
        local_date=date,
        duration_minutes__isnull=False,
        start__isnull=True,
        end__isnull=True,
    )

    total_minutes = 0
    for session in sessions:
        overlap_start = max(session.start, start_utc)
        overlap_end = min(session.end, end_utc)
        seconds = max(0, (overlap_end - overlap_start).total_seconds())
        total_minutes += int(seconds // 60)

    for session in duration_only_sessions:
        total_minutes += session.duration_minutes or 0

    blocks = ScheduleBlock.objects.filter(user=user, date=date)
    planned_minutes = 0
    for block in blocks:
        if block.start_time and block.end_time:
            start_dt = dt.datetime.combine(date, block.start_time)
            end_dt = dt.datetime.combine(date, block.end_time)
            planned_minutes += int((end_dt - start_dt).total_seconds() // 60)
        elif block.duration_minutes:
            planned_minutes += int(block.duration_minutes)

    completion_rate = None
    if planned_minutes > 0:
        completion_rate = total_minutes / planned_minutes

    return {
        "total_minutes": total_minutes,
        "planned_minutes": planned_minutes,
        "completion_rate": completion_rate,
        "sessions_count": sessions.count() + duration_only_sessions.count(),
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


def compute_category_totals(user, start_date, end_date):
    start_utc, _ = get_day_bounds_utc(user, start_date)
    _, end_utc = get_day_bounds_utc(user, end_date)

    category_map = {
        category.pk: {
            "id": category.pk,
            "name": category.name,
            "actual_minutes": 0,
            "planned_minutes": 0,
            "intensity_score": 0,
        }
        for category in ActivityCategory.objects.filter(user=user).order_by("name")
    }
    category_map.setdefault(
        None,
        {
            "id": None,
            "name": "Unassigned",
            "actual_minutes": 0,
            "planned_minutes": 0,
            "intensity_score": 0,
        },
    )

    sessions = (
        Session.objects.filter(
            user=user,
            end__isnull=False,
            start__lt=end_utc,
            end__gt=start_utc,
        )
        .select_related("activity", "category", "activity__category")
        .order_by("start")
    )

    for session in sessions:
        overlap_start = max(session.start, start_utc)
        overlap_end = min(session.end, end_utc)
        minutes = int(max(0, (overlap_end - overlap_start).total_seconds()) // 60)
        if minutes <= 0:
            continue
        category = session.category or (session.activity.category if session.activity else None)
        category_id = category.pk if category else None
        priority = session.activity.priority if session.activity else 1
        bucket = category_map.setdefault(
            category_id,
            {
                "id": category_id,
                "name": category.name if category else "Unassigned",
                "actual_minutes": 0,
                "planned_minutes": 0,
                "intensity_score": 0,
            },
        )
        bucket["actual_minutes"] += minutes
        bucket["intensity_score"] += minutes * max(1, priority)

    duration_only_sessions = Session.objects.filter(
        user=user,
        local_date__range=(start_date, end_date),
        duration_minutes__isnull=False,
        start__isnull=True,
        end__isnull=True,
    ).select_related("activity", "category", "activity__category")

    for session in duration_only_sessions:
        minutes = session.duration_minutes or 0
        if minutes <= 0:
            continue
        category = session.category or (session.activity.category if session.activity else None)
        category_id = category.pk if category else None
        priority = session.activity.priority if session.activity else 1
        bucket = category_map.setdefault(
            category_id,
            {
                "id": category_id,
                "name": category.name if category else "Unassigned",
                "actual_minutes": 0,
                "planned_minutes": 0,
                "intensity_score": 0,
            },
        )
        bucket["actual_minutes"] += minutes
        bucket["intensity_score"] += minutes * max(1, priority)

    blocks = ScheduleBlock.objects.filter(user=user, date__range=(start_date, end_date)).select_related(
        "activity", "category"
    )
    for block in blocks:
        minutes = 0
        if block.start_time and block.end_time:
            start_dt = dt.datetime.combine(block.date, block.start_time)
            end_dt = dt.datetime.combine(block.date, block.end_time)
            minutes = int((end_dt - start_dt).total_seconds() // 60)
        elif block.duration_minutes:
            minutes = int(block.duration_minutes)
        if minutes <= 0:
            continue
        category = block.category or (block.activity.category if block.activity else None)
        category_id = category.pk if category else None
        bucket = category_map.setdefault(
            category_id,
            {
                "id": category_id,
                "name": category.name if category else "Unassigned",
                "actual_minutes": 0,
                "planned_minutes": 0,
                "intensity_score": 0,
            },
        )
        bucket["planned_minutes"] += minutes

    return list(category_map.values())


def compute_daily_intensity(user, date):
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

    intensity = 0
    for session in sessions:
        overlap_start = max(session.start, start_utc)
        overlap_end = min(session.end, end_utc)
        minutes = int(max(0, (overlap_end - overlap_start).total_seconds()) // 60)
        if minutes <= 0:
            continue
        priority = session.activity.priority if session.activity else 1
        intensity += minutes * max(1, priority)

    duration_only_sessions = Session.objects.filter(
        user=user,
        local_date=date,
        duration_minutes__isnull=False,
        start__isnull=True,
        end__isnull=True,
    ).select_related("activity")
    for session in duration_only_sessions:
        minutes = session.duration_minutes or 0
        if minutes <= 0:
            continue
        priority = session.activity.priority if session.activity else 1
        intensity += minutes * max(1, priority)

    return intensity
