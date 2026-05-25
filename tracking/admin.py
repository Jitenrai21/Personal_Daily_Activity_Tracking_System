from django.contrib import admin

from tracking.models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "activity",
        "category",
        "local_date",
        "start_time",
        "end_time",
        "duration_minutes",
        "start",
        "end",
        "source",
    )
    list_filter = ("source",)
    search_fields = ("user__username", "user__email", "activity__title")
