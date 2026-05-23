from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from activities.forms import ActivityForm, CategoryForm, RecurrenceRuleForm
from activities.models import Activity, ActivityCategory, RecurrenceRule


@login_required
def category_list_view(request):
    categories = ActivityCategory.objects.filter(user=request.user).order_by("name")
    return render(
        request, "activities/category_list.html", {"categories": categories}
    )


@login_required
def category_create_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            return redirect("category_list")
    else:
        form = CategoryForm()
    return render(request, "activities/category_form.html", {"form": form})


@login_required
def category_update_view(request, pk):
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "activities/category_form.html", {"form": form})


@login_required
def category_delete_view(request, pk):
    category = get_object_or_404(ActivityCategory, pk=pk, user=request.user)
    if request.method == "POST":
        category.delete()
        return redirect("category_list")
    return render(
        request, "activities/category_confirm_delete.html", {"category": category}
    )


@login_required
def activity_list_view(request):
    activities = (
        Activity.objects.filter(user=request.user)
        .select_related("category")
        .order_by("-updated_at")
    )
    return render(
        request, "activities/activity_list.html", {"activities": activities}
    )


@login_required
def activity_detail_view(request, pk):
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    return render(request, "activities/activity_detail.html", {"activity": activity})


@login_required
def activity_create_view(request):
    if request.method == "POST":
        form = ActivityForm(request.POST, user=request.user)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.user = request.user
            activity.save()
            return redirect("activity_list")
    else:
        form = ActivityForm(user=request.user)
    return render(request, "activities/activity_form.html", {"form": form})


@login_required
def activity_update_view(request, pk):
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    if request.method == "POST":
        form = ActivityForm(request.POST, instance=activity, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("activity_detail", pk=activity.pk)
    else:
        form = ActivityForm(instance=activity, user=request.user)
    return render(request, "activities/activity_form.html", {"form": form})


@login_required
def activity_delete_view(request, pk):
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    if request.method == "POST":
        activity.delete()
        return redirect("activity_list")
    return render(
        request, "activities/activity_confirm_delete.html", {"activity": activity}
    )


@login_required
def recurrence_edit_view(request, activity_id):
    activity = get_object_or_404(Activity, pk=activity_id, user=request.user)
    recurrence, _ = RecurrenceRule.objects.get_or_create(activity=activity)

    if request.method == "POST":
        form = RecurrenceRuleForm(request.POST, instance=recurrence)
        if form.is_valid():
            form.save()
            return redirect("activity_detail", pk=activity.pk)
    else:
        form = RecurrenceRuleForm(instance=recurrence)

    return render(
        request,
        "activities/recurrence_form.html",
        {"form": form, "activity": activity},
    )


@login_required
@require_POST
def activity_toggle_active_view(request, pk):
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    activity.is_active = not activity.is_active
    activity.save(update_fields=["is_active", "updated_at"])
    if request.headers.get("HX-Request"):
        return render(
            request,
            "activities/partials/activity_row.html",
            {"activity": activity},
        )
    return JsonResponse({"id": activity.pk, "is_active": activity.is_active})


@login_required
@require_POST
def activity_quick_target_view(request, pk):
    activity = get_object_or_404(Activity, pk=pk, user=request.user)
    raw_value = request.POST.get("target_value")
    try:
        target_value = int(raw_value)
    except (TypeError, ValueError):
        return HttpResponse("Invalid target", status=400)

    if target_value <= 0:
        return HttpResponse("Target must be > 0", status=400)

    activity.target_value = target_value
    activity.save(update_fields=["target_value", "updated_at"])

    if request.headers.get("HX-Request"):
        return render(
            request,
            "activities/partials/activity_row.html",
            {"activity": activity},
        )
    return JsonResponse({"id": activity.pk, "target_value": activity.target_value})
