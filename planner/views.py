import datetime as dt

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from planner.forms import ScheduleBlockForm, WeeklyRoutineForm
from planner.models import ScheduleBlock, WeeklyRoutine
from planner.services import generate_blocks_for_date


@login_required
def daily_plan_view(request):
    date_str = request.GET.get("date")
    if date_str:
        date = dt.date.fromisoformat(date_str)
    else:
        date = dt.date.today()

    blocks = ScheduleBlock.objects.filter(user=request.user, date=date)
    form = ScheduleBlockForm(user=request.user, initial={"date": date})

    return render(
        request,
        "planner/daily_plan.html",
        {
            "date": date,
            "blocks": blocks,
            "form": form,
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
        if request.headers.get("HX-Request"):
            return render(
                request,
                "planner/partials/schedule_row.html",
                {"block": block},
            )
        return redirect("planner_day")

    blocks = ScheduleBlock.objects.filter(user=request.user, date=form.data.get("date"))
    return render(
        request,
        "planner/daily_plan.html",
        {"date": form.data.get("date"), "blocks": blocks, "form": form},
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
def routine_list_view(request):
    routines = WeeklyRoutine.objects.filter(user=request.user).select_related("activity")
    form = WeeklyRoutineForm(user=request.user)
    return render(
        request,
        "planner/routine_list.html",
        {"routines": routines, "form": form},
    )


@login_required
@require_POST
def routine_create_view(request):
    form = WeeklyRoutineForm(request.POST, user=request.user)
    if form.is_valid():
        routine = form.save(commit=False)
        routine.user = request.user
        routine.save()
        if request.headers.get("HX-Request"):
            return render(
                request,
                "planner/partials/routine_row.html",
                {"routine": routine},
            )
        return redirect("routine_list")

    routines = WeeklyRoutine.objects.filter(user=request.user)
    return render(
        request,
        "planner/routine_list.html",
        {"routines": routines, "form": form},
    )


@login_required
@require_POST
def routine_delete_view(request, pk):
    routine = get_object_or_404(WeeklyRoutine, pk=pk, user=request.user)
    routine.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("routine_list")


@login_required
@require_POST
def generate_day_view(request):
    date_str = request.POST.get("date")
    date = dt.date.fromisoformat(date_str)
    generate_blocks_for_date(request.user, date)
    blocks = ScheduleBlock.objects.filter(user=request.user, date=date)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "planner/partials/schedule_list.html",
            {"blocks": blocks},
        )
    return redirect("planner_day")
