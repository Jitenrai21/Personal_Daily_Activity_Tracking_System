from django.contrib import admin

from analytics.models import AggregatedDaily


@admin.register(AggregatedDaily)
class AggregatedDailyAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "total_minutes",
        "planned_minutes",
        "completion_rate",
    )
    list_filter = ("date",)
    search_fields = ("user__username", "user__email")
