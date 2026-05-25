from django.contrib import admin

from planner.models import ScheduleBlock


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = (
        "activity",
        "category",
        "user",
        "date",
        "start_time",
        "end_time",
        "duration_minutes",
    )
    list_filter = ("date",)
    search_fields = ("activity__title", "user__username", "user__email")
