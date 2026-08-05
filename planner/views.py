import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from activities.models import Activity, ActivityCategory
from planner.forms import PlannerActivityForm, PlannerCategoryForm, ScheduleBlockForm
from planner.models import ScheduleBlock
from tracking.models import Session
from tracking.services import (
    pause_timer_session,
    resume_timer_session,
    start_timer_session,
    stop_timer_session,
)


def _parse_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        try:
            return (
                dt.datetime.strptime(value, "%B %d, %Y")
                .replace(tzinfo=dt.timezone.utc)
                .date()
            )
        except ValueError:
            return None


def _planner_context(
    user, date, schedule_form=None, category_form=None, activity_form=None
):
    blocks = ScheduleBlock.objects.filter(user=user, date=date).select_related(
        "activity", "category"
    )
    running_session = (
        Session.objects.filter(user=user, end__isnull=True, source=Session.SOURCE_TIMER)
        .select_related("activity")
        .first()
    )
    categories = ActivityCategory.objects.filter(user=user).order_by("name")
    activities = (
        Activity.objects.filter(user=user).select_related("category").order_by("title")
    )
    activity_choices = activities
    return {
        "date": date,
        "blocks": blocks,
        "running_session": running_session,
        "categories": categories,
        "activities": activities,
        "activity_choices": activity_choices,
        "form": schedule_form or ScheduleBlockForm(user=user, initial={"date": date}),
        "category_form": category_form or PlannerCategoryForm(),
        "activity_form": activity_form or PlannerActivityForm(user=user),
    }


def _planner_timer_row_response(request, block):
    running_session = (
        Session.objects.filter(
            user=request.user, end__isnull=True, source=Session.SOURCE_TIMER
        )
        .select_related("activity")
        .first()
    )
    if request.headers.get("HX-Request"):
        return render(
            request,
            "planner/partials/schedule_row.html",
            {
                "block": block,
                "running_session": running_session,
            },
        )
    return redirect("planner_day")


def _block_timer_session(user, block):
    session = (
        Session.objects.filter(user=user, end__isnull=True, source=Session.SOURCE_TIMER)
        .select_related("activity")
        .first()
    )
    if not session:
        return None

    metadata = session.metadata if isinstance(session.metadata, dict) else {}
    if str(metadata.get("planned_block_id")) != str(block.pk):
        return None
    return session


@login_required
def daily_plan_view(request):
    date_str = request.GET.get("date")
    date = _parse_date(date_str) or dt.datetime.now(dt.timezone.utc).date()

    return render(
        request, "planner/daily_plan.html", _planner_context(request.user, date)
    )


@login_required
@require_POST
def schedule_block_create_view(request):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    form = ScheduleBlockForm(request.POST, user=request.user)
    if form.is_valid():
        block = form.save(commit=False)
        block.user = request.user
        block.full_clean()
        block.save()
        running_session = (
            Session.objects.filter(
                user=request.user, end__isnull=True, source=Session.SOURCE_TIMER
            )
            .select_related("activity")
            .first()
        )
        if request.headers.get("HX-Request"):
            return render(
                request,
                "planner/partials/schedule_row.html",
                {
                    "block": block,
                    "running_session": running_session,
                },
            )
        return redirect("planner_day")

    return render(
        request,
        "planner/daily_plan.html",
        _planner_context(request.user, date, schedule_form=form),
    )


@login_required
@require_POST
def schedule_block_delete_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    block.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("planner_day")


@login_required
@require_POST
def schedule_block_start_timer_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    metadata = {
        "planned_block_id": block.pk,
        "planned_date": block.date.isoformat(),
        "planned_start_time": (
            block.start_time.isoformat() if block.start_time else None
        ),
        "planned_end_time": block.end_time.isoformat() if block.end_time else None,
        "planned_duration_minutes": block.duration_minutes,
    }

    _, running = start_timer_session(
        user=request.user,
        activity=block.activity,
        notes=(block.notes or "").strip(),
        metadata=metadata,
    )
    if running:
        return HttpResponse("Timer already running.", status=409)

    return _planner_timer_row_response(request, block)


@login_required
@require_POST
def schedule_block_pause_timer_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    active_session = _block_timer_session(request.user, block)
    if not active_session:
        return HttpResponse("No active session to pause.", status=400)

    paused = pause_timer_session(request.user)
    if not paused:
        return HttpResponse("No active session to pause.", status=400)

    return _planner_timer_row_response(request, block)


@login_required
@require_POST
def schedule_block_resume_timer_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    active_session = _block_timer_session(request.user, block)
    if not active_session:
        return HttpResponse("No paused session to resume.", status=400)

    resumed = resume_timer_session(request.user)
    if not resumed:
        return HttpResponse("No paused session to resume.", status=400)

    return _planner_timer_row_response(request, block)


@login_required
@require_POST
def schedule_block_stop_timer_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    stopped = stop_timer_session(request.user)
    if not stopped:
        return HttpResponse("No active session to stop.", status=400)

    return _planner_timer_row_response(request, block)


@login_required
@require_POST
def planner_category_create_view(request):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    form = PlannerCategoryForm(request.POST)
    if form.is_valid():
        category = form.save(commit=False)
        category.user = request.user
        category.save()
        return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")

    context = _planner_context(request.user, date, category_form=form)
    return render(request, "planner/daily_plan.html", context)


@login_required
@require_POST
def planner_category_update_view(request, pk):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    form = PlannerCategoryForm(request.POST, instance=category)
    if form.is_valid():
        form.save()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


@login_required
@require_POST
def planner_category_delete_view(request, pk):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    category.delete()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


@login_required
@require_POST
def planner_activity_create_view(request):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    form = PlannerActivityForm(request.POST, user=request.user)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.user = request.user
        activity.save()
        return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")

    context = _planner_context(request.user, date, activity_form=form)
    return render(request, "planner/daily_plan.html", context)


@login_required
@require_POST
def planner_activity_update_view(request, pk):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    form = PlannerActivityForm(request.POST, instance=activity, user=request.user)
    if form.is_valid():
        updated = form.save(commit=False)
        updated.user = request.user
        updated.save()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


@login_required
@require_POST
def planner_activity_delete_view(request, pk):
    date = (
        _parse_date(request.POST.get("date")) or dt.datetime.now(dt.timezone.utc).date()
    )
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    activity.delete()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


# ── Feature: Edit schedule block ─────────────────────────────────


@login_required
def schedule_block_edit_form_view(request, pk):
    """Return an inline edit form for a schedule block (GET)."""
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    form = ScheduleBlockForm(instance=block, user=request.user)
    activities = Activity.objects.filter(user=request.user).select_related("category")
    categories = ActivityCategory.objects.filter(user=request.user)
    running_session = _block_timer_session(request.user, block)
    return render(
        request,
        "planner/partials/schedule_edit_form.html",
        {
            "form": form,
            "block": block,
            "activities": activities,
            "categories": categories,
            "running_session": running_session,
        },
    )


@login_required
@require_POST
def schedule_block_update_view(request, pk):
    """Process the edit form submission for a schedule block (POST)."""
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    form = ScheduleBlockForm(request.POST, instance=block, user=request.user)

    if request.headers.get("HX-Request"):
        if form.is_valid():
            form.save()
            running_session = _block_timer_session(request.user, block)
            return render(
                request,
                "planner/partials/schedule_row.html",
                {"block": block, "running_session": running_session},
            )
        activities = Activity.objects.filter(user=request.user).select_related(
            "category"
        )
        categories = ActivityCategory.objects.filter(user=request.user)
        running_session = _block_timer_session(request.user, block)
        return render(
            request,
            "planner/partials/schedule_edit_form.html",
            {
                "form": form,
                "block": block,
                "activities": activities,
                "categories": categories,
                "running_session": running_session,
            },
        )

    if form.is_valid():
        form.save()
        return redirect(f"{reverse('planner_day')}?date={block.date.isoformat()}")

    context = _planner_context(request.user, block.date, schedule_form=form)
    return render(request, "planner/daily_plan.html", context)


# ── Feature: View a single schedule block row ───────────────────


@login_required
def schedule_block_row_view(request, pk):
    """Return a single schedule row partial (for cancel/reload)."""
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    running_session = _block_timer_session(request.user, block)
    return render(
        request,
        "planner/partials/schedule_row.html",
        {"block": block, "running_session": running_session},
    )


# ── Feature: Copy previous day's plan ───────────────────────────


@login_required
@require_POST
def copy_previous_day_plan_view(request):
    date_str = request.POST.get("date")
    date = _parse_date(date_str) or dt.datetime.now(dt.timezone.utc).date()
    prev_date = date - dt.timedelta(days=1)

    prev_blocks = ScheduleBlock.objects.filter(user=request.user, date=prev_date)
    for prev_block in prev_blocks:
        ScheduleBlock.objects.create(
            user=request.user,
            activity=prev_block.activity,
            category=prev_block.category,
            date=date,
            start_time=prev_block.start_time,
            end_time=prev_block.end_time,
            duration_minutes=prev_block.duration_minutes,
            notes=prev_block.notes,
        )

    if request.headers.get("HX-Request"):
        blocks = ScheduleBlock.objects.filter(
            user=request.user, date=date
        ).select_related("activity", "category")
        return render(
            request,
            "planner/partials/schedule_list.html",
            {"blocks": blocks, "date": date},
        )

    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")
