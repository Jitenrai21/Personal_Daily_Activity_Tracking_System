import csv
from zoneinfo import ZoneInfo

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from activities.models import Activity
from tracking.forms import SessionLogForm
from tracking.models import Session
from tracking.services import start_timer_session
from users.models import UserProfile


def get_user_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def get_running_session(user):
    return (
        Session.objects.filter(user=user, end__isnull=True)
        .select_related("activity")
        .first()
    )


@login_required
def session_list_view(request):
    profile = get_user_profile(request.user)
    activity_map = Activity.objects.filter(user=request.user).select_related("category")
    activity_choices = Activity.objects.filter(user=request.user).select_related(
        "category"
    )
    activities = Activity.objects.filter(user=request.user).order_by(
        "title"
    )
    sessions = Session.objects.filter(user=request.user).select_related(
        "activity", "category"
    )
    sessions = sessions.order_by("-local_date", "-start")
    running_session = get_running_session(request.user)
    form = SessionLogForm(user=request.user)
    return render(
        request,
        "tracking/session_list.html",
        {
            "sessions": sessions,
            "form": form,
            "running_session": running_session,
            "profile": profile,
            "activities": activities,
            "activity_choices": activity_choices,
            "activity_map": activity_map,
        },
    )


@login_required
@require_POST
def session_start_view(request):
    activity_id = request.POST.get("activity_id")
    activity = None
    if activity_id:
        activity = Activity.objects.filter(
            pk=activity_id, user=request.user
        ).first()
    notes = (request.POST.get("notes") or "").strip()
    planned_block_id = request.POST.get("planned_block_id")
    metadata = None
    if planned_block_id:
        metadata = {"planned_block_id": planned_block_id}

    session, running = start_timer_session(
        user=request.user,
        activity=activity,
        notes=notes,
        metadata=metadata,
    )
    if running:
        if request.headers.get("HX-Request"):
            return HttpResponse("Timer already running.", status=409)
        messages.error(request, "A timer is already running.")
        return redirect("session_list")

    running_session = get_running_session(request.user)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "tracking/partials/start_stop_button.html",
            {
                "running_session": running_session,
                "target_id": request.POST.get("target_id", "session-toggle"),
                "activity": activity,
                "activities": Activity.objects.filter(
                    user=request.user
                ).order_by("title"),
            },
        )
    return redirect("session_list")


@login_required
@require_POST
def session_stop_view(request):
    running_session = get_running_session(request.user)
    if not running_session:
        if request.headers.get("HX-Request"):
            return HttpResponse("No active session.", status=400)
        messages.error(request, "No active session to stop.")
        return redirect("session_list")

    profile = get_user_profile(request.user)
    tz = ZoneInfo(profile.timezone)
    now = timezone.now()
    local_now = now.astimezone(tz)
    running_session.end = now
    running_session.end_time = local_now.time().replace(microsecond=0)
    running_session.full_clean()
    running_session.save(update_fields=["end", "end_time", "duration_minutes", "updated_at"])

    running_session = get_running_session(request.user)
    activity = None
    activity_id = request.POST.get("activity_id")
    if activity_id:
        activity = Activity.objects.filter(
            pk=activity_id, user=request.user
        ).first()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "tracking/partials/start_stop_button.html",
            {
                "running_session": running_session,
                "target_id": request.POST.get("target_id", "session-toggle"),
                "activity": activity,
                "activities": Activity.objects.filter(
                    user=request.user
                ).order_by("title"),
            },
        )
    return redirect("session_list")


@login_required
@require_POST
def session_log_view(request):
    form = SessionLogForm(request.POST, user=request.user)
    if form.is_valid():
        session = form.save(commit=False)
        session.user = request.user
        session.source = Session.SOURCE_MANUAL
        session.save()
        if request.headers.get("HX-Request"):
            profile = get_user_profile(request.user)
            return render(
                request,
                "tracking/partials/session_row.html",
                {"session": session, "profile": profile},
            )
        return redirect("session_list")

    profile = get_user_profile(request.user)
    activity_map = Activity.objects.filter(user=request.user).select_related("category")
    activity_choices = Activity.objects.filter(user=request.user).select_related(
        "category"
    )
    sessions = Session.objects.filter(user=request.user).select_related(
        "activity", "category"
    )
    sessions = sessions.order_by("-local_date", "-start")
    running_session = get_running_session(request.user)
    activities = Activity.objects.filter(user=request.user).order_by(
        "title"
    )
    return render(
        request,
        "tracking/session_list.html",
        {
            "sessions": sessions,
            "form": form,
            "running_session": running_session,
            "profile": profile,
            "activities": activities,
            "activity_choices": activity_choices,
            "activity_map": activity_map,
        },
    )


@login_required
def session_detail_view(request, pk):
    session = get_object_or_404(Session, pk=pk, user=request.user)
    profile = get_user_profile(request.user)
    activity_map = Activity.objects.filter(user=request.user).select_related("category")
    activity_choices = Activity.objects.filter(user=request.user).select_related(
        "category"
    )
    form = SessionLogForm(instance=session, user=request.user)
    return render(
        request,
        "tracking/session_detail.html",
        {
            "session": session,
            "form": form,
            "profile": profile,
            "activity_choices": activity_choices,
            "activity_map": activity_map,
        },
    )


@login_required
@require_POST
def session_update_view(request, pk):
    session = get_object_or_404(Session, pk=pk, user=request.user)
    form = SessionLogForm(request.POST, instance=session, user=request.user)
    if form.is_valid():
        updated = form.save(commit=False)
        updated.source = session.source
        updated.user = request.user
        updated.save()
        if request.headers.get("HX-Request"):
            profile = get_user_profile(request.user)
            return render(
                request,
                "tracking/partials/session_row.html",
                {"session": updated, "profile": profile},
            )
        return redirect("session_detail", pk=session.pk)

    profile = get_user_profile(request.user)
    return render(
        request,
        "tracking/session_detail.html",
        {"session": session, "form": form, "profile": profile},
    )


@login_required
@require_POST
def session_delete_view(request, pk):
    session = get_object_or_404(Session, pk=pk, user=request.user)
    session.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("session_list")


@login_required
def session_export_csv_view(request):
    profile = get_user_profile(request.user)
    local_tz = ZoneInfo(profile.timezone)
    sessions = Session.objects.filter(user=request.user).select_related("activity", "category")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=sessions.csv"

    writer = csv.writer(response)
    writer.writerow(
        [
            "id",
            "activity",
            "category",
            "date",
            "start_time",
            "end_time",
            "start_utc",
            "end_utc",
            "duration_minutes",
            "source",
            "notes",
        ]
    )
    for session in sessions:
        start_local = session.start.astimezone(local_tz) if session.start else None
        end_local = session.end.astimezone(local_tz) if session.end else None
        local_date = session.local_date
        start_time = session.start_time
        end_time = session.end_time
        if not local_date and start_local:
            local_date = start_local.date()
            start_time = start_local.time().replace(microsecond=0)
        if not end_time and end_local:
            end_time = end_local.time().replace(microsecond=0)
        writer.writerow(
            [
                session.pk,
                session.activity.title if session.activity else "",
                session.category.name if session.category else "",
                local_date.isoformat() if local_date else "",
                start_time.isoformat() if start_time else "",
                end_time.isoformat() if end_time else "",
                session.start.isoformat() if session.start else "",
                session.end.isoformat() if session.end else "",
                session.duration_minutes or "",
                session.source,
                session.notes,
            ]
        )

    return response


@login_required
def session_export_json_view(request):
    profile = get_user_profile(request.user)
    local_tz = ZoneInfo(profile.timezone)
    sessions = Session.objects.filter(user=request.user).select_related("activity", "category")

    payload = []
    for session in sessions:
        start_local = session.start.astimezone(local_tz) if session.start else None
        end_local = session.end.astimezone(local_tz) if session.end else None
        local_date = session.local_date
        start_time = session.start_time
        end_time = session.end_time
        if not local_date and start_local:
            local_date = start_local.date()
            start_time = start_local.time().replace(microsecond=0)
        if not end_time and end_local:
            end_time = end_local.time().replace(microsecond=0)
        payload.append(
            {
                "id": session.pk,
                "activity": session.activity.title if session.activity else None,
                "category": session.category.name if session.category else None,
                "date": local_date.isoformat() if local_date else None,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "start_utc": session.start.isoformat() if session.start else None,
                "end_utc": session.end.isoformat() if session.end else None,
                "start_local": start_local.isoformat() if start_local else None,
                "end_local": end_local.isoformat() if end_local else None,
                "duration_minutes": session.duration_minutes,
                "source": session.source,
                "notes": session.notes,
            }
        )

    return JsonResponse({"sessions": payload})
