from django.contrib import admin

from activities.models import Activity, ActivityCategory, RecurrenceRule


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "user", "is_default", "is_archived")
	search_fields = ("name", "user__username", "user__email")
	list_filter = ("is_default", "is_archived")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
	list_display = ("title", "user", "category", "target_type", "target_value")
	search_fields = ("title", "user__username", "user__email")
	list_filter = ("target_type", "is_active")


@admin.register(RecurrenceRule)
class RecurrenceRuleAdmin(admin.ModelAdmin):
	list_display = ("activity", "frequency", "interval", "start_date", "end_date")
	list_filter = ("frequency",)
