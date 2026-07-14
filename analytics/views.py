import datetime as dt
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from activities.models import Activity, ActivityCategory
from analytics.models import AggregatedDaily, DailyReflection, DailyScore
from analytics.reflection import ensure_daily_reflection
from analytics.scoring import upsert_daily_score
from analytics.services import (
    compute_category_totals,
    compute_daily_intensity,
    get_day_bounds_utc,
    get_user_timezone,
)
from planner.models import ScheduleBlock
from tracking.models import Session


RANGE_OPTIONS = [7, 30, 90]
NUM_HEATMAP_WEEKS = 6


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


def _resolve_dashboard_date_range(request, local_today, default_days):
    raw_from = (request.GET.get("from_date") or "").strip()
    raw_to = (request.GET.get("to_date") or "").strip()

    if not raw_from and not raw_to:
        return None, None, False

    start_date = _parse_date(raw_from) if raw_from else None
    end_date = _parse_date(raw_to) if raw_to else None

    if end_date is None:
        end_date = local_today
    if start_date is None:
        start_date = end_date - dt.timedelta(days=default_days - 1)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    return start_date, end_date, True


def get_activity_filter(request, user):
    raw = request.GET.get("activity")
    if raw and raw.isdigit():
        return Activity.objects.filter(user=user, pk=int(raw)).first()
    return None


def build_daily_series(user, start_date, end_date, category=None, activity=None):
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
                seconds = max(
                    0,
                    (overlap_end - overlap_start).total_seconds()
                    - (session.paused_seconds or 0),
                )
                total_minutes += int(seconds // 60)
            totals[date] = total_minutes
            sessions_count[date] = sessions.count()

            blocks = ScheduleBlock.objects.filter(
                user=user, date=date, activity=activity
            )
            planned_minutes = 0
            for block in blocks:
                if block.start_time and block.end_time:
                    start_dt = dt.datetime.combine(date, block.start_time)
                    end_dt = dt.datetime.combine(date, block.end_time)
                    planned_minutes += int((end_dt - start_dt).total_seconds() // 60)
                elif block.duration_minutes:
                    planned_minutes += int(block.duration_minutes)
            planned[date] = planned_minutes
    elif category:
        totals = {}
        planned = {}
        sessions_count = {}
        for date in dates:
            start_utc, end_utc = get_day_bounds_utc(user, date)
            sessions = Session.objects.filter(
                user=user,
                end__isnull=False,
                start__lt=end_utc,
                end__gt=start_utc,
            ).filter(
                Q(category=category)
                | Q(category__isnull=True, activity__category=category)
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
            totals[date] = total_minutes

            duration_only_sessions = Session.objects.filter(
                user=user,
                local_date=date,
                duration_minutes__isnull=False,
                start__isnull=True,
                end__isnull=True,
            ).filter(
                Q(category=category)
                | Q(category__isnull=True, activity__category=category)
            )
            duration_minutes = sum(
                session.duration_minutes or 0 for session in duration_only_sessions
            )
            totals[date] += duration_minutes
            sessions_count[date] = sessions.count() + duration_only_sessions.count()

            blocks = ScheduleBlock.objects.filter(user=user, date=date).filter(
                Q(category=category)
                | Q(category__isnull=True, activity__category=category)
            )
            planned_minutes = 0
            for block in blocks:
                if block.start_time and block.end_time:
                    start_dt = dt.datetime.combine(date, block.start_time)
                    end_dt = dt.datetime.combine(date, block.end_time)
                    planned_minutes += int((end_dt - start_dt).total_seconds() // 60)
                elif block.duration_minutes:
                    planned_minutes += int(block.duration_minutes)
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


def build_category_daily_series(user, start_date, end_date, dates, labels):
    categories = list(ActivityCategory.objects.filter(user=user).order_by("name"))

    def make_bucket(category_id, category_name):
        return {
            "id": category_id,
            "key": str(category_id) if category_id is not None else "unassigned",
            "name": category_name,
            "actual": {date: 0 for date in dates},
            "planned": {date: 0 for date in dates},
            "activity_breakdown": {date: [] for date in dates},
            "_activity_lookup": {date: {} for date in dates},
        }

    def get_bucket(category_id, category_name):
        bucket = category_map.get(category_id)
        if bucket is None:
            bucket = make_bucket(category_id, category_name)
            category_map[category_id] = bucket
        return bucket

    def add_activity_minutes(bucket, date, activity, kind, minutes):
        if date not in bucket["activity_breakdown"]:
            return

        activity_id = activity.pk if activity else None
        activity_key = activity_id if activity_id is not None else "unassigned"
        activity_name = activity.title if activity else "Unassigned"
        description = (activity.notes or "").strip() if activity else ""
        lookup = bucket["_activity_lookup"][date]
        entry = lookup.get(activity_key)
        if entry is None:
            entry = {
                "id": activity_id,
                "key": str(activity_key),
                "name": activity_name,
                "description": description,
                "actual": 0,
                "planned": 0,
            }
            lookup[activity_key] = entry
            bucket["activity_breakdown"][date].append(entry)

        if description and not entry["description"]:
            entry["description"] = description
        entry[kind] += minutes

    category_map = {
        category.pk: make_bucket(category.pk, category.name) for category in categories
    }
    session_rows = (
        Session.objects.filter(
            user=user,
            local_date__range=(start_date, end_date),
            duration_minutes__isnull=False,
        )
        .select_related("activity", "activity__category", "category")
        .annotate(resolved_category_id=Coalesce("category_id", "activity__category_id"))
        .order_by("local_date", "activity__title")
    )

    for session in session_rows:
        category = session.category or (
            session.activity.category if session.activity else None
        )
        category_id = session.resolved_category_id
        date = session.local_date
        minutes = session.duration_minutes or 0
        if minutes <= 0:
            continue

        bucket = get_bucket(category_id, category.name if category else "Unassigned")
        if date in bucket["actual"]:
            bucket["actual"][date] += minutes
            add_activity_minutes(bucket, date, session.activity, "actual", minutes)

    blocks = (
        ScheduleBlock.objects.filter(user=user, date__range=(start_date, end_date))
        .select_related("activity", "category")
        .order_by("date")
    )
    for block in blocks:
        category = block.category or (
            block.activity.category if block.activity else None
        )
        category_id = category.pk if category else None
        minutes = 0
        if block.start_time and block.end_time:
            start_dt = dt.datetime.combine(block.date, block.start_time)
            end_dt = dt.datetime.combine(block.date, block.end_time)
            minutes = int((end_dt - start_dt).total_seconds() // 60)
        elif block.duration_minutes:
            minutes = int(block.duration_minutes)
        if minutes <= 0:
            continue
        bucket = get_bucket(category_id, category.name if category else "Unassigned")
        if block.date in bucket["planned"]:
            bucket["planned"][block.date] += minutes
            add_activity_minutes(bucket, block.date, block.activity, "planned", minutes)

    ordered_ids = [category.pk for category in categories]
    series = []
    for category_id in ordered_ids:
        bucket = category_map.get(category_id)
        if not bucket:
            continue
        activity_breakdown = []
        for date in dates:
            day_entries = list(bucket["activity_breakdown"][date])
            day_entries.sort(
                key=lambda item: (item["actual"] + item["planned"], item["name"]),
                reverse=True,
            )
            activity_breakdown.append(day_entries)
        series.append(
            {
                "id": bucket["id"],
                "key": bucket["key"],
                "name": bucket["name"],
                "labels": labels,
                "actual": [bucket["actual"][date] for date in dates],
                "planned": [bucket["planned"][date] for date in dates],
                "activity_breakdown": activity_breakdown,
            }
        )

    return series


def aggregate_weekly(dates, actual, planned):
    buckets = {}
    for date, actual_value, planned_value in zip(dates, actual, planned):
        week_start = date - dt.timedelta(days=date.weekday())
        bucket = buckets.setdefault(week_start, {"actual": 0, "planned": 0})
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
        bucket = buckets.setdefault(key, {"actual": 0, "planned": 0})
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


def _intensity_level(value):
    if value == 0:
        return 0
    if value <= 300:
        return 1
    if value <= 500:
        return 2
    if value <= 700:
        return 3
    return 4


def build_heatmap(dates, intensity):
    total_map = {date: value for date, value in zip(dates, intensity)}
    if not total_map:
        return []

    weeks = []
    current = dates[0]
    last = dates[-1]

    while current <= last:
        week = []
        for _ in range(7):
            value = total_map.get(current, 0)
            week.append(
                {
                    "date": current.isoformat(),
                    "value": value,
                    "level": _intensity_level(value),
                }
            )
            current += dt.timedelta(days=1)
        weeks.append(week)

    return weeks


def build_kpis(total_actual, total_planned, streak, category_totals):
    completion_rate = None
    if total_planned > 0:
        completion_rate = round(total_actual / total_planned * 100)

    top_category = None
    if category_totals:
        top_category = max(category_totals, key=lambda item: item["intensity_score"])

    return {
        "total_actual": total_actual,
        "total_planned": total_planned,
        "completion_rate": completion_rate,
        "streak": streak,
        "top_category": top_category,
    }


def _compute_global_streak(user, local_today):
    """
    Counts consecutive days with positive intensity ending on or before
    local_today, walking backwards from today through all history.
    Ignores the dashboard date range filter entirely.
    """
    streak = 0
    current = local_today
    while True:
        intensity = compute_daily_intensity(user, current)
        if intensity <= 0:
            break
        streak += 1
        current -= dt.timedelta(days=1)
    return streak


def build_context(request):
    user = request.user
    days = parse_range(request)
    tz = get_user_timezone(user)
    local_today = timezone.now().astimezone(tz).date()

    custom_start_date, custom_end_date, custom_range_active = (
        _resolve_dashboard_date_range(
            request,
            local_today,
            days,
        )
    )

    year_options = build_year_options(user, tz, local_today)
    if custom_range_active:
        start_date = custom_start_date
        end_date = custom_end_date
        selected_year = end_date.year
    else:
        selected_year = parse_year(request, year_options, local_today.year)

        if selected_year == local_today.year:
            end_date = local_today
        else:
            end_date = dt.date(selected_year, 12, 31)

        start_date = end_date - dt.timedelta(days=days - 1)
        year_start = dt.date(selected_year, 1, 1)
        if start_date < year_start:
            start_date = year_start

    series = build_daily_series(user, start_date, end_date)

    category_totals = compute_category_totals(user, start_date, end_date)
    category_chart_rows = [
        row
        for row in category_totals
        if row["actual_minutes"] > 0 or row["planned_minutes"] > 0
    ]
    if not category_chart_rows:
        category_chart_rows = category_totals
    category_labels = [row["name"] for row in category_chart_rows]
    category_actual = [row["actual_minutes"] for row in category_chart_rows]
    category_planned = [row["planned_minutes"] for row in category_chart_rows]

    weekly_labels, weekly_actual, weekly_planned = aggregate_weekly(
        series["dates"], series["actual"], series["planned"]
    )
    monthly_labels, monthly_actual, monthly_planned = aggregate_monthly(
        series["dates"], series["actual"], series["planned"]
    )

    heatmap_start = local_today - dt.timedelta(days=NUM_HEATMAP_WEEKS * 7 - 1)
    heatmap_dates = [
        heatmap_start + dt.timedelta(days=i) for i in range(NUM_HEATMAP_WEEKS * 7)
    ]
    heatmap_intensity = [compute_daily_intensity(user, d) for d in heatmap_dates]
    heatmap = build_heatmap(heatmap_dates, heatmap_intensity)

    # Compute streak from full history up to today — never filtered
    streak = _compute_global_streak(user, local_today)

    kpis = build_kpis(
        total_actual=sum(series["actual"]),
        total_planned=sum(series["planned"]),
        streak=streak,
        category_totals=category_totals,
    )

    category_daily_series = build_category_daily_series(
        user,
        start_date,
        end_date,
        series["dates"],
        series["labels"],
    )

    return {
        "range_days": (end_date - start_date).days + 1,
        "range_options": RANGE_OPTIONS,
        "year_options": year_options,
        "selected_year": selected_year,
        "from_date_value": start_date.isoformat(),
        "to_date_value": end_date.isoformat(),
        "daily_labels": series["labels"],
        "daily_actual": series["actual"],
        "daily_planned": series["planned"],
        "weekly_labels": weekly_labels,
        "weekly_actual": weekly_actual,
        "weekly_planned": weekly_planned,
        "monthly_labels": monthly_labels,
        "monthly_actual": monthly_actual,
        "monthly_planned": monthly_planned,
        "category_totals": category_totals,
        "category_labels": category_labels,
        "category_actual": category_actual,
        "category_planned": category_planned,
        "category_daily_series": category_daily_series,
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
    response = render(request, "analytics/partials/dashboard_content.html", context)
    query = request.GET.urlencode()
    response["HX-Push-Url"] = (
        f"{reverse('dashboard')}?{query}" if query else reverse("dashboard")
    )
    return response


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

    start = _parse_date(request.GET.get("from_date") or request.GET.get("start"))
    end = _parse_date(request.GET.get("to_date") or request.GET.get("end"))

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

    return JsonResponse(
        {"start": start.isoformat(), "end": end.isoformat(), "items": payload}
    )


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

    return JsonResponse(
        {"start": start.isoformat(), "end": end.isoformat(), "items": items}
    )


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
