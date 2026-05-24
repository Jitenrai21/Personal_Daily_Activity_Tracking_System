from django.urls import path

from analytics import views

urlpatterns = [
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("dashboard/partial/", views.dashboard_partial_view, name="dashboard_partial"),
    path("api/metrics/daily/", views.metrics_daily_view, name="metrics_daily"),
    path("api/metrics/weekly/", views.metrics_weekly_view, name="metrics_weekly"),
    path("api/metrics/monthly/", views.metrics_monthly_view, name="metrics_monthly"),
    path("api/metrics/heatmap/", views.metrics_heatmap_view, name="metrics_heatmap"),
]
