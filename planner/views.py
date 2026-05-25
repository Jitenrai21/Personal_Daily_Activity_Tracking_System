import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from activities.models import Activity
from planner.forms import ScheduleBlockForm
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


@login_required
def daily_plan_view(request):
    date_str = request.GET.get("date")
    date = _parse_date(date_str) or dt.date.today()

    blocks = ScheduleBlock.objects.filter(user=request.user, date=date).select_related(
        "activity", "category"
    )
    form = ScheduleBlockForm(user=request.user, initial={"date": date})
    running_session = (
        Session.objects.filter(user=request.user, end__isnull=True)
        .select_related("activity")
        .first()
    )
    activity_map = Activity.objects.filter(user=request.user).select_related("category")
    activity_choices = Activity.objects.filter(
        user=request.user, is_active=True
    ).select_related("category")

    return render(
        request,
        "planner/daily_plan.html",
        {
            "date": date,
            "blocks": blocks,
            "form": form,
            "running_session": running_session,
            "activity_map": activity_map,
            "activity_choices": activity_choices,
        },
    )


@login_required
@require_POST
def schedule_block_create_view(request):
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

    blocks = ScheduleBlock.objects.filter(user=request.user, date=form.data.get("date")).select_related(
        "activity", "category"
    )
    running_session = (
        Session.objects.filter(user=request.user, end__isnull=True)
        .select_related("activity")
        .first()
    )
    activity_map = Activity.objects.filter(user=request.user).select_related("category")
    activity_choices = Activity.objects.filter(
        user=request.user, is_active=True
    ).select_related("category")
    return render(
        request,
        "planner/daily_plan.html",
        {
            "date": form.data.get("date"),
            "blocks": blocks,
            "form": form,
            "running_session": running_session,
            "activity_map": activity_map,
            "activity_choices": activity_choices,
        },
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
