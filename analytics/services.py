import datetime as dt
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from activities.models import ActivityCategory
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
    return local_start.astimezone(dt.timezone.utc), local_end.astimezone(
        dt.timezone.utc
    )


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
        seconds = max(
            0,
            (overlap_end - overlap_start).total_seconds()
            - (session.paused_seconds or 0),
        )
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
        seconds = max(
            0,
            (overlap_end - overlap_start).total_seconds()
            - (session.paused_seconds or 0),
        )
        minutes = int(seconds // 60)
        if minutes <= 0:
            continue
        category = session.category or (
            session.activity.category if session.activity else None
        )
        category_id = category.pk if category else None
        weight = session.activity.weight if session.activity else 1
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
        bucket["intensity_score"] += minutes * max(1, weight)

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
        category = session.category or (
            session.activity.category if session.activity else None
        )
        category_id = category.pk if category else None
        weight = session.activity.weight if session.activity else 1
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
        bucket["intensity_score"] += minutes * max(1, weight)

    blocks = ScheduleBlock.objects.filter(
        user=user, date__range=(start_date, end_date)
    ).select_related("activity", "category")
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
        category = block.category or (
            block.activity.category if block.activity else None
        )
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


<<<<<<< HEAD
=======
def day_meets_plan(actual_minutes, planned_minutes):
    """
    A day meets its plan when there is tracked activity and actual time
    does not fall short of planned time.

    - planned > 0: success only when actual >= planned
    - planned == 0: any actual activity counts (nothing to miss)
    - empty day (0, 0): does not count — idle days break streaks
    """
    return actual_minutes > 0 and actual_minutes >= planned_minutes


def _aggregate_day_map(user, end_date):
    return {
        row.date: row
        for row in AggregatedDaily.objects.filter(user=user, date__lte=end_date)
    }


def _streak_stats(day_map, local_today, day_ok, grace_today=True):
    """
    Walk day_map to derive current and best streaks.

    grace_today: if the in-progress local_today does not qualify yet,
    count the streak ending yesterday instead of resetting to zero.
    """

    def meets(day):
        row = day_map.get(day)
        return bool(row) and day_ok(row)

    days = 0
    cursor = local_today
    if grace_today and not meets(cursor):
        cursor -= dt.timedelta(days=1)
    while meets(cursor):
        days += 1
        cursor -= dt.timedelta(days=1)

    best = 0
    if day_map:
        run = 0
        cursor = min(day_map)
        while cursor <= local_today:
            if meets(cursor):
                run += 1
                best = max(best, run)
            else:
                run = 0
            cursor += dt.timedelta(days=1)

    is_record = days > 0 and days >= best
    return days, best, is_record


def compute_intensity_streak(user, local_today):
    """Consecutive local days with any tracked activity (total_minutes > 0)."""
    day_map = _aggregate_day_map(user, local_today)
    days, best, is_record = _streak_stats(
        day_map,
        local_today,
        day_ok=lambda row: row.total_minutes > 0,
    )
    return {"days": days, "best": best, "is_record": is_record}


def compute_plan_streak(user, local_today):
    """
    Consecutive local days where actual minutes met planned minutes
    (see day_meets_plan). Uses AggregatedDaily totals — categories are
    not required for the day to count.
    """
    day_map = _aggregate_day_map(user, local_today)
    days, best, is_record = _streak_stats(
        day_map,
        local_today,
        day_ok=lambda row: day_meets_plan(row.total_minutes, row.planned_minutes),
    )
    return {"days": days, "best": best, "is_record": is_record}


def compute_category_plan_streaks(user, local_today, lookback_days=400):
    """
    Per-category plan-fulfillment streaks over a lookback window.

    Returns a list of:
      {id, name, streak, met_days}
    where streak is consecutive days (ending today/yesterday) that meet
    day_meets_plan for that category, and met_days is how many days in
    the window had planned > 0 and actual >= planned.
    """
    start_date = local_today - dt.timedelta(days=lookback_days)

    categories = list(ActivityCategory.objects.filter(user=user).order_by("name"))
    cat_names = {category.pk: category.name for category in categories}

    actual_by_day = {}
    planned_by_day = {}

    def resolve_category_id(direct_category, activity):
        if direct_category_id := getattr(direct_category, "pk", None):
            return direct_category_id
        if activity is not None and activity.category_id:
            return activity.category_id
        return None

    sessions = (
        Session.objects.filter(
            user=user,
            local_date__range=(start_date, local_today),
            duration_minutes__isnull=False,
        )
        .select_related("activity", "activity__category", "category")
    )
    for session in sessions:
        minutes = session.duration_minutes or 0
        if minutes <= 0:
            continue
        category_id = resolve_category_id(session.category, session.activity)
        day_actual = actual_by_day.setdefault(session.local_date, {})
        day_actual[category_id] = day_actual.get(category_id, 0) + minutes

    blocks = ScheduleBlock.objects.filter(
        user=user, date__range=(start_date, local_today)
    ).select_related("activity", "category")
    for block in blocks:
        if block.start_time and block.end_time:
            start_dt = dt.datetime.combine(block.date, block.start_time)
            end_dt = dt.datetime.combine(block.date, block.end_time)
            minutes = int((end_dt - start_dt).total_seconds() // 60)
        elif block.duration_minutes:
            minutes = int(block.duration_minutes)
        else:
            minutes = 0
        if minutes <= 0:
            continue
        category_id = resolve_category_id(block.category, block.activity)
        day_planned = planned_by_day.setdefault(block.date, {})
        day_planned[category_id] = day_planned.get(category_id, 0) + minutes

    category_ids = set(cat_names)
    for day_map in (actual_by_day, planned_by_day):
        for day_minutes in day_map.values():
            category_ids.update(day_minutes)

    results = []
    for category_id in category_ids:
        def meets(day, category_id=category_id):
            actual = actual_by_day.get(day, {}).get(category_id, 0)
            planned = planned_by_day.get(day, {}).get(category_id, 0)
            return day_meets_plan(actual, planned)

        streak = 0
        cursor = local_today
        if not meets(cursor):
            cursor -= dt.timedelta(days=1)
        while cursor >= start_date and meets(cursor):
            streak += 1
            cursor -= dt.timedelta(days=1)

        met_days = 0
        cursor = start_date
        while cursor <= local_today:
            actual = actual_by_day.get(cursor, {}).get(category_id, 0)
            planned = planned_by_day.get(cursor, {}).get(category_id, 0)
            if planned > 0 and actual >= planned:
                met_days += 1
            cursor += dt.timedelta(days=1)

        results.append(
            {
                "id": category_id,
                "name": cat_names.get(category_id, "Unassigned"),
                "streak": streak,
                "met_days": met_days,
            }
        )

    return sorted(results, key=lambda item: (item["name"] or "").lower())


>>>>>>> master
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
        seconds = max(
            0,
            (overlap_end - overlap_start).total_seconds()
            - (session.paused_seconds or 0),
        )
        minutes = int(seconds // 60)
        if minutes <= 0:
            continue
        weight = session.activity.weight if session.activity else 1
        intensity += minutes * max(1, weight)

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
        weight = session.activity.weight if session.activity else 1
        intensity += minutes * max(1, weight)

    return intensity
