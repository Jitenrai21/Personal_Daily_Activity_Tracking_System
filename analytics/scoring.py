import datetime as dt
import math

from django.db import transaction

from analytics.models import DailyScore
from analytics.services import get_day_bounds_utc, get_user_timezone, update_daily
from planner.models import ScheduleBlock
from tracking.models import Session
from users.models import UserProfile


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _session_minutes_by_category(user, local_date):
    start_utc, end_utc = get_day_bounds_utc(user, local_date)
    sessions = Session.objects.filter(
        user=user,
        end__isnull=False,
        start__lt=end_utc,
        end__gt=start_utc,
    ).select_related("activity", "activity__category", "category")

    duration_only_sessions = Session.objects.filter(
        user=user,
        local_date=local_date,
        duration_minutes__isnull=False,
        start__isnull=True,
        end__isnull=True,
    ).select_related("activity", "activity__category", "category")

    category_minutes = {}
    total_minutes = 0
    late_minutes = 0
    tz = get_user_timezone(user)

    for session in sessions:
        overlap_start = max(session.start, start_utc)
        overlap_end = min(session.end, end_utc)
        minutes = int(max(0, (overlap_end - overlap_start).total_seconds()) // 60)
        if minutes <= 0:
            continue

        category_name = "Unassigned"
        if session.category:
            category_name = session.category.name
        elif session.activity and session.activity.category:
            category_name = session.activity.category.name
        category_minutes[category_name] = category_minutes.get(category_name, 0) + minutes
        total_minutes += minutes

        local_start = overlap_start.astimezone(tz)
        local_end = overlap_end.astimezone(tz)
        cursor = local_start
        while cursor < local_end:
            next_step = min(local_end, cursor + dt.timedelta(minutes=15))
            if cursor.hour >= 22 or cursor.hour < 5:
                late_minutes += int((next_step - cursor).total_seconds() // 60)
            cursor = next_step

    for session in duration_only_sessions:
        minutes = session.duration_minutes or 0
        if minutes <= 0:
            continue
        category_name = "Unassigned"
        if session.category:
            category_name = session.category.name
        elif session.activity and session.activity.category:
            category_name = session.activity.category.name
        category_minutes[category_name] = category_minutes.get(category_name, 0) + minutes
        total_minutes += minutes

    return (
        category_minutes,
        total_minutes,
        late_minutes,
        sessions.count() + duration_only_sessions.count(),
    )


def _planned_minutes(user, local_date):
    blocks = ScheduleBlock.objects.filter(user=user, date=local_date)
    minutes = 0
    for block in blocks:
        start_dt = dt.datetime.combine(local_date, block.start_time)
        end_dt = dt.datetime.combine(local_date, block.end_time)
        minutes += int((end_dt - start_dt).total_seconds() // 60)
    return minutes


def compute_daily_score(user, local_date):
    aggregate = update_daily(user, local_date)
    category_minutes, total_minutes, late_minutes, sessions_count = _session_minutes_by_category(
        user, local_date
    )
    planned_minutes = aggregate.planned_minutes

    if planned_minutes > 0:
        discipline = clamp((total_minutes / planned_minutes) * 100)
    else:
        discipline = 70.0 if total_minutes > 0 else 40.0

    if total_minutes <= 0:
        balance = 50.0
    else:
        active = [minutes for minutes in category_minutes.values() if minutes > 0]
        if len(active) <= 1:
            balance = 40.0
        else:
            shares = [m / total_minutes for m in active]
            entropy = -sum(p * math.log(p) for p in shares if p > 0)
            max_entropy = math.log(len(active))
            balance = clamp((entropy / max_entropy) * 100 if max_entropy else 40.0)

    profile = UserProfile.objects.filter(user=user).first()
    sleep_target = profile.sleep_target_minutes if profile else 480
    daily_focus = profile.daily_focus_minutes if profile else 120
    late_penalty = (late_minutes / max(sleep_target, 1)) * 100
    overload_penalty = 0.0
    overload_threshold = max(daily_focus * 2, 180)
    if total_minutes > overload_threshold:
        overload_penalty = ((total_minutes - overload_threshold) / overload_threshold) * 40
    recovery = clamp(100 - late_penalty - overload_penalty)

    composite = round((0.45 * discipline) + (0.30 * balance) + (0.25 * recovery), 2)

    explanation = {
        "planned_minutes": planned_minutes,
        "actual_minutes": total_minutes,
        "sessions_count": sessions_count,
        "late_minutes": late_minutes,
        "category_minutes": category_minutes,
        "formula": {
            "discipline": "planned_vs_actual",
            "balance": "category_entropy",
            "recovery": "late_load_and_overload_penalty",
            "composite": "0.45*discipline + 0.30*balance + 0.25*recovery",
        },
    }

    return {
        "discipline_score": round(discipline, 2),
        "balance_score": round(balance, 2),
        "recovery_score": round(recovery, 2),
        "composite_score": composite,
        "explanation_json": explanation,
    }


def upsert_daily_score(user, local_date):
    metrics = compute_daily_score(user, local_date)
    with transaction.atomic():
        score, _ = DailyScore.objects.get_or_create(user=user, local_date=local_date)
        score.discipline_score = metrics["discipline_score"]
        score.balance_score = metrics["balance_score"]
        score.recovery_score = metrics["recovery_score"]
        score.composite_score = metrics["composite_score"]
        score.explanation_json = metrics["explanation_json"]
        score.version = "v1"
        score.save()
    return score


def rebuild_scores(user, days):
    tz = get_user_timezone(user)
    today = dt.datetime.now(tz).date()
    output = []
    for offset in range(days):
        local_date = today - dt.timedelta(days=offset)
        output.append(upsert_daily_score(user, local_date))
    return output
