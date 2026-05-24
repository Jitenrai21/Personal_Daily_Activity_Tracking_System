from django.contrib import admin

from planner.models import ScheduleBlock, WeeklyRoutine


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ("activity", "user", "date", "start_time", "end_time", "source")
    list_filter = ("source", "date")
    search_fields = ("activity__title", "user__username", "user__email")


@admin.register(WeeklyRoutine)
class WeeklyRoutineAdmin(admin.ModelAdmin):
    list_display = ("activity", "user", "weekday", "start_time", "end_time", "is_active")
    list_filter = ("weekday", "is_active")
    search_fields = ("activity__title", "user__username", "user__email")
