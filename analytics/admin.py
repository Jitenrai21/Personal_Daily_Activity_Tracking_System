from django.contrib import admin

from analytics.models import AggregatedDaily, DailyReflection, DailyScore


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


@admin.register(DailyScore)
class DailyScoreAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "local_date",
        "discipline_score",
        "balance_score",
        "recovery_score",
        "composite_score",
    )
    list_filter = ("local_date",)
    search_fields = ("user__username", "user__email")


@admin.register(DailyReflection)
class DailyReflectionAdmin(admin.ModelAdmin):
    list_display = ("user", "local_date", "mood", "updated_at")
    list_filter = ("mood", "local_date")
    search_fields = ("user__username", "user__email", "prompt_text", "answer_text")
