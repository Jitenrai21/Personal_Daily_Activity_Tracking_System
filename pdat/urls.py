from django.contrib import admin
from django.urls import path

from pdat.views import health_view

urlpatterns = [
    path("", health_view, name="health"),
    path("admin/", admin.site.urls),
]
