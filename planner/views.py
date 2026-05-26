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
from tracking.services import start_timer_session, stop_timer_session


def _parse_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        try:
            return dt.datetime.strptime(value, "%B %d, %Y").date()
        except ValueError:
            return None


def _planner_context(user, date, schedule_form=None, category_form=None, activity_form=None):
    blocks = ScheduleBlock.objects.filter(user=user, date=date).select_related(
        "activity", "category"
    )
    running_session = (
        Session.objects.filter(user=user, end__isnull=True)
        .select_related("activity")
        .first()
    )
    categories = ActivityCategory.objects.filter(user=user).order_by("name")
    activities = Activity.objects.filter(user=user).select_related("category").order_by("title")
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


@login_required
def daily_plan_view(request):
    date_str = request.GET.get("date")
    date = _parse_date(date_str) or dt.date.today()

    return render(request, "planner/daily_plan.html", _planner_context(request.user, date))


@login_required
@require_POST
def schedule_block_create_view(request):
    date = _parse_date(request.POST.get("date")) or dt.date.today()
    form = ScheduleBlockForm(request.POST, user=request.user)
    if form.is_valid():
        block = form.save(commit=False)
        block.user = request.user
        block.full_clean()
        block.save()
        running_session = (
            Session.objects.filter(user=request.user, end__isnull=True)
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
        "planned_start_time": block.start_time.isoformat() if block.start_time else None,
        "planned_end_time": block.end_time.isoformat() if block.end_time else None,
        "planned_duration_minutes": block.duration_minutes,
    }

    session, running = start_timer_session(
        user=request.user,
        activity=block.activity,
        notes=(block.notes or "").strip(),
        metadata=metadata,
    )
    if running:
        return HttpResponse("Timer already running.", status=409)

    running_session = session
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


@login_required
@require_POST
def schedule_block_stop_timer_view(request, pk):
    block = get_object_or_404(ScheduleBlock, pk=pk, user=request.user)
    stopped = stop_timer_session(request.user)
    if not stopped:
        return HttpResponse("No active session to stop.", status=400)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "planner/partials/schedule_row.html",
            {
                "block": block,
                "running_session": None,
            },
        )
    return redirect("planner_day")


@login_required
@require_POST
def planner_category_create_view(request):
    date = _parse_date(request.POST.get("date")) or dt.date.today()
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
    date = _parse_date(request.POST.get("date")) or dt.date.today()
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    form = PlannerCategoryForm(request.POST, instance=category)
    if form.is_valid():
        form.save()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


@login_required
@require_POST
def planner_category_delete_view(request, pk):
    date = _parse_date(request.POST.get("date")) or dt.date.today()
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    category.delete()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")


@login_required
@require_POST
def planner_activity_create_view(request):
    date = _parse_date(request.POST.get("date")) or dt.date.today()
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
    date = _parse_date(request.POST.get("date")) or dt.date.today()
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
    date = _parse_date(request.POST.get("date")) or dt.date.today()
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    activity.delete()
    return redirect(f"{reverse('planner_day')}?date={date.isoformat()}")
