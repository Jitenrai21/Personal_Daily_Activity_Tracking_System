from django.contrib import admin
from django.urls import include, path

from pdat.views import health_view

urlpatterns = [
    path("", health_view, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/", include("users.urls")),
    path("activities/", include("activities.urls")),
    path("planner/", include("planner.urls")),
    path("tracking/", include("tracking.urls")),
    path("", include("analytics.urls")),
]
