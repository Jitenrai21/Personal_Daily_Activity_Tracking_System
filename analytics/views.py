import datetime as dt
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from activities.models import Activity
from analytics.models import AggregatedDaily, DailyReflection, DailyScore
from analytics.reflection import ensure_daily_reflection
from analytics.scoring import upsert_daily_score
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


def build_year_options(user, tz, fallback_date):
    candidates = []
    first_agg = AggregatedDaily.objects.filter(user=user).order_by("date").first()
    last_agg = AggregatedDaily.objects.filter(user=user).order_by("-date").first()
    if first_agg:
        candidates.append(first_agg.date)
    if last_agg:
        candidates.append(last_agg.date)

    first_plan = ScheduleBlock.objects.filter(user=user).order_by("date").first()
    last_plan = ScheduleBlock.objects.filter(user=user).order_by("-date").first()
    if first_plan:
        candidates.append(first_plan.date)
    if last_plan:
        candidates.append(last_plan.date)

    first_session = Session.objects.filter(user=user).order_by("start").first()
    last_session = Session.objects.filter(user=user).order_by("-start").first()
    if first_session and first_session.start:
        candidates.append(first_session.start.astimezone(tz).date())
    if last_session and last_session.start:
        candidates.append(last_session.start.astimezone(tz).date())

    if not candidates:
        candidates = [fallback_date]

    min_date = min(candidates)
    max_date = max(candidates)

    return list(range(min_date.year, max_date.year + 1))


def parse_year(request, year_options, fallback_year):
    raw_year = request.GET.get("year")
    if raw_year and raw_year.isdigit():
        year = int(raw_year)
        if year in year_options:
            return year
    return fallback_year


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

    year_options = build_year_options(user, tz, local_today)
    selected_year = parse_year(request, year_options, local_today.year)

    if selected_year == local_today.year:
        end_date = local_today
    else:
        end_date = dt.date(selected_year, 12, 31)

    start_date = end_date - dt.timedelta(days=days - 1)
    year_start = dt.date(selected_year, 1, 1)
    if start_date < year_start:
        start_date = year_start

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
        "year_options": year_options,
        "selected_year": selected_year,
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


def _parse_date(raw_value):
    if not raw_value:
        return None
    try:
        return dt.date.fromisoformat(raw_value)
    except ValueError:
        return None


def _resolve_date_range(request, default_days=30):
    tz = get_user_timezone(request.user)
    local_today = timezone.now().astimezone(tz).date()

    start = _parse_date(request.GET.get("start"))
    end = _parse_date(request.GET.get("end"))

    if not end:
        end = local_today
    if not start:
        start = end - dt.timedelta(days=default_days - 1)

    if start > end:
        start, end = end, start

    return start, end


@login_required
def scores_daily_api_view(request):
    start, end = _resolve_date_range(request)
    dates = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]

    rows = DailyScore.objects.filter(
        user=request.user,
        local_date__range=(start, end),
    )
    row_map = {row.local_date: row for row in rows}

    payload = []
    for local_date in dates:
        score = row_map.get(local_date)
        payload.append(
            {
                "local_date": local_date.isoformat(),
                "discipline_score": score.discipline_score if score else None,
                "balance_score": score.balance_score if score else None,
                "recovery_score": score.recovery_score if score else None,
                "composite_score": score.composite_score if score else None,
            }
        )

    return JsonResponse({"start": start.isoformat(), "end": end.isoformat(), "items": payload})


@login_required
def score_detail_api_view(request, date):
    local_date = _parse_date(date)
    if not local_date:
        return HttpResponseBadRequest("Invalid date format.")

    score = upsert_daily_score(request.user, local_date)
    reflection = ensure_daily_reflection(score)

    return JsonResponse(
        {
            "local_date": local_date.isoformat(),
            "discipline_score": score.discipline_score,
            "balance_score": score.balance_score,
            "recovery_score": score.recovery_score,
            "composite_score": score.composite_score,
            "version": score.version,
            "computed_at": score.computed_at.isoformat(),
            "explanation": score.explanation_json,
            "reflection": {
                "id": reflection.pk,
                "prompt_text": reflection.prompt_text,
                "answer_text": reflection.answer_text,
                "mood": reflection.mood,
                "tags": reflection.tags,
            },
        }
    )


@login_required
@require_http_methods(["POST"])
def reflections_create_api_view(request):
    local_date = _parse_date(request.POST.get("local_date"))
    if not local_date:
        return HttpResponseBadRequest("local_date is required in YYYY-MM-DD format.")

    score = upsert_daily_score(request.user, local_date)
    reflection = ensure_daily_reflection(score)

    prompt_text = request.POST.get("prompt_text")
    answer_text = request.POST.get("answer_text")
    mood = request.POST.get("mood")
    tags_raw = request.POST.get("tags")

    if prompt_text:
        reflection.prompt_text = prompt_text
    if answer_text is not None:
        reflection.answer_text = answer_text
    if mood in {"great", "good", "neutral", "low"}:
        reflection.mood = mood
    if tags_raw:
        try:
            parsed = json.loads(tags_raw)
            if isinstance(parsed, list):
                reflection.tags = parsed
        except json.JSONDecodeError:
            pass

    reflection.save()
    return JsonResponse(
        {
            "id": reflection.pk,
            "local_date": reflection.local_date.isoformat(),
            "prompt_text": reflection.prompt_text,
            "answer_text": reflection.answer_text,
            "mood": reflection.mood,
            "tags": reflection.tags,
        }
    )


@login_required
@require_http_methods(["PATCH"])
def reflections_update_api_view(request, pk):
    reflection = DailyReflection.objects.filter(user=request.user, pk=pk).first()
    if not reflection:
        return HttpResponseBadRequest("Reflection not found.")

    payload = {}
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON payload.")

    if "prompt_text" in payload:
        reflection.prompt_text = payload["prompt_text"]
    if "answer_text" in payload:
        reflection.answer_text = payload["answer_text"]
    if payload.get("mood") in {"great", "good", "neutral", "low"}:
        reflection.mood = payload["mood"]
    if isinstance(payload.get("tags"), list):
        reflection.tags = payload["tags"]

    reflection.save()
    return JsonResponse(
        {
            "id": reflection.pk,
            "local_date": reflection.local_date.isoformat(),
            "prompt_text": reflection.prompt_text,
            "answer_text": reflection.answer_text,
            "mood": reflection.mood,
            "tags": reflection.tags,
        }
    )


@login_required
def reflections_history_api_view(request):
    start, end = _resolve_date_range(request)
    reflections = DailyReflection.objects.filter(
        user=request.user,
        local_date__range=(start, end),
    ).order_by("-local_date")

    items = []
    for reflection in reflections:
        score = DailyScore.objects.filter(
            user=request.user,
            local_date=reflection.local_date,
        ).first()
        items.append(
            {
                "id": reflection.pk,
                "local_date": reflection.local_date.isoformat(),
                "prompt_text": reflection.prompt_text,
                "answer_text": reflection.answer_text,
                "mood": reflection.mood,
                "tags": reflection.tags,
                "composite_score": score.composite_score if score else None,
            }
        )

    return JsonResponse({"start": start.isoformat(), "end": end.isoformat(), "items": items})


@login_required
def reflection_history_view(request):
    start, end = _resolve_date_range(request)
    reflections = DailyReflection.objects.filter(
        user=request.user,
        local_date__range=(start, end),
    ).order_by("-local_date")

    entries = []
    score_map = {
        score.local_date: score
        for score in DailyScore.objects.filter(
            user=request.user,
            local_date__range=(start, end),
        )
    }
    for reflection in reflections:
        entries.append(
            {
                "local_date": reflection.local_date,
                "prompt_text": reflection.prompt_text,
                "answer_text": reflection.answer_text,
                "mood": reflection.mood,
                "tags": reflection.tags,
                "score": score_map.get(reflection.local_date),
            }
        )

    return render(
        request,
        "analytics/reflection_history.html",
        {"entries": entries, "start": start, "end": end},
    )
