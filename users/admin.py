from django.contrib import admin

from users.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "sleep_target_minutes")
    search_fields = ("user__username", "user__email")
