import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from activities.models import Activity
from analytics.models import AggregatedDaily
from analytics.services import get_day_bounds_utc, get_user_timezone
from planner.models import ScheduleBlock
from tracking.models import Session


RANGE_OPTIONS = [7, 30, 90]


def parse_range(request):
    range_raw = request.GET.get("range")
    if range_raw and range_raw.isdigit():
        days = int(range_raw)
    else:
        days = 30

    if days not in RANGE_OPTIONS:
        days = 30

    return days


def get_activity_filter(request, user):
    raw = request.GET.get("activity")
    if raw and raw.isdigit():
        return Activity.objects.filter(user=user, pk=int(raw)).first()
    return None


def build_daily_series(user, start_date, end_date, activity=None):
    days = (end_date - start_date).days + 1
    dates = [start_date + dt.timedelta(days=offset) for offset in range(days)]

    if activity:
        totals = {}
        planned = {}
        sessions_count = {}
        for date in dates:
            start_utc, end_utc = get_day_bounds_utc(user, date)
            sessions = Session.objects.filter(
                user=user,
                activity=activity,
                end__isnull=False,
                start__lt=end_utc,
                end__gt=start_utc,
            )
            total_minutes = 0
            for session in sessions:
                overlap_start = max(session.start, start_utc)
                overlap_end = min(session.end, end_utc)
                total_minutes += int(
                    max(0, (overlap_end - overlap_start).total_seconds()) // 60
                )
            totals[date] = total_minutes
            sessions_count[date] = sessions.count()

            blocks = ScheduleBlock.objects.filter(
                user=user, date=date, activity=activity
            )
            planned_minutes = 0
            for block in blocks:
                start_dt = dt.datetime.combine(date, block.start_time)
                end_dt = dt.datetime.combine(date, block.end_time)
                planned_minutes += int((end_dt - start_dt).total_seconds() // 60)
            planned[date] = planned_minutes
    else:
        aggregates = AggregatedDaily.objects.filter(
            user=user, date__range=(start_date, end_date)
        )
        aggregate_map = {row.date: row for row in aggregates}
        totals = {}
        planned = {}
        sessions_count = {}
        for date in dates:
            row = aggregate_map.get(date)
            totals[date] = row.total_minutes if row else 0
            planned[date] = row.planned_minutes if row else 0
            sessions_count[date] = row.sessions_count if row else 0

    labels = [date.isoformat() for date in dates]
    actual = [totals[date] for date in dates]
    planned_values = [planned[date] for date in dates]

    return {
        "dates": dates,
        "labels": labels,
        "actual": actual,
        "planned": planned_values,
        "sessions_count": [sessions_count[date] for date in dates],
    }


def aggregate_weekly(dates, actual, planned):
    buckets = {}
    for date, actual_value, planned_value in zip(dates, actual, planned):
        week_start = date - dt.timedelta(days=date.weekday())
        bucket = buckets.setdefault(
            week_start, {"actual": 0, "planned": 0}
        )
        bucket["actual"] += actual_value
        bucket["planned"] += planned_value

    labels = []
    actual_values = []
    planned_values = []
    for week_start in sorted(buckets.keys()):
        labels.append(week_start.isoformat())
        actual_values.append(buckets[week_start]["actual"])
        planned_values.append(buckets[week_start]["planned"])

    return labels, actual_values, planned_values


def aggregate_monthly(dates, actual, planned):
    buckets = {}
    for date, actual_value, planned_value in zip(dates, actual, planned):
        key = dt.date(date.year, date.month, 1)
        bucket = buckets.setdefault(key, {"actual": 0, "planned": 0}
        )
        bucket["actual"] += actual_value
        bucket["planned"] += planned_value

    labels = []
    actual_values = []
    planned_values = []
    for month_start in sorted(buckets.keys()):
        labels.append(month_start.strftime("%Y-%m"))
        actual_values.append(buckets[month_start]["actual"])
        planned_values.append(buckets[month_start]["planned"])

    return labels, actual_values, planned_values


def build_heatmap(dates, actual):
    total_map = {date: value for date, value in zip(dates, actual)}
    if not total_map:
        return []

    max_value = max(total_map.values()) or 1
    weeks = []
    start_date = dates[0]
    offset = start_date.weekday()
    current = start_date - dt.timedelta(days=offset)
    last = dates[-1]

    while current <= last:
        week = []
        for _ in range(7):
            value = total_map.get(current, 0)
            level = int((value / max_value) * 4) if value else 0
            week.append({
                "date": current.isoformat(),
                "value": value,
                "level": level,
            })
            current += dt.timedelta(days=1)
        weeks.append(week)

    return weeks


def build_kpis(dates, actual, planned):
    total_actual = sum(actual)
    total_planned = sum(planned)
    completion_rate = None
    if total_planned > 0:
        completion_rate = round(total_actual / total_planned * 100)

    streak = 0
    for value in reversed(actual):
        if value <= 0:
            break
        streak += 1

    today_actual = actual[-1] if actual else 0
    today_planned = planned[-1] if planned else 0

    return {
        "total_actual": total_actual,
        "total_planned": total_planned,
        "completion_rate": completion_rate,
        "streak": streak,
        "today_actual": today_actual,
        "today_planned": today_planned,
    }


def build_context(request):
    user = request.user
    days = parse_range(request)
    tz = get_user_timezone(user)
    local_today = timezone.now().astimezone(tz).date()
    start_date = local_today - dt.timedelta(days=days - 1)

    activity = get_activity_filter(request, user)
    series = build_daily_series(user, start_date, local_today, activity)

    weekly_labels, weekly_actual, weekly_planned = aggregate_weekly(
        series["dates"], series["actual"], series["planned"]
    )
    monthly_labels, monthly_actual, monthly_planned = aggregate_monthly(
        series["dates"], series["actual"], series["planned"]
    )

    heatmap = build_heatmap(series["dates"], series["actual"])
    kpis = build_kpis(series["dates"], series["actual"], series["planned"])

    activities = Activity.objects.filter(user=user).order_by("title")

    return {
        "range_days": days,
        "range_options": RANGE_OPTIONS,
        "activity": activity,
        "activities": activities,
        "daily_labels": series["labels"],
        "daily_actual": series["actual"],
        "daily_planned": series["planned"],
        "weekly_labels": weekly_labels,
        "weekly_actual": weekly_actual,
        "weekly_planned": weekly_planned,
        "monthly_labels": monthly_labels,
        "monthly_actual": monthly_actual,
        "monthly_planned": monthly_planned,
        "heatmap": heatmap,
        "kpis": kpis,
        "local_today": local_today,
    }


@login_required
def dashboard_view(request):
    context = build_context(request)
    return render(request, "analytics/dashboard.html", context)


@login_required
def dashboard_partial_view(request):
    context = build_context(request)
    return render(request, "analytics/partials/dashboard_content.html", context)


@login_required
def metrics_daily_view(request):
    context = build_context(request)
    return JsonResponse(
        {
            "labels": context["daily_labels"],
            "actual": context["daily_actual"],
            "planned": context["daily_planned"],
        }
    )


@login_required
def metrics_weekly_view(request):
    context = build_context(request)
    return JsonResponse(
        {
            "labels": context["weekly_labels"],
            "actual": context["weekly_actual"],
            "planned": context["weekly_planned"],
        }
    )


@login_required
def metrics_monthly_view(request):
    context = build_context(request)
    return JsonResponse(
        {
            "labels": context["monthly_labels"],
            "actual": context["monthly_actual"],
            "planned": context["monthly_planned"],
        }
    )


@login_required
def metrics_heatmap_view(request):
    context = build_context(request)
    return JsonResponse({"weeks": context["heatmap"]})
