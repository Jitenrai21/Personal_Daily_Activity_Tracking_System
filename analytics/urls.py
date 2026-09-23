from django.urls import path

from analytics import views

urlpatterns = [
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("dashboard/partial/", views.dashboard_partial_view, name="dashboard_partial"),
    path(
        "reflections/history/", views.reflection_history_view, name="reflection_history"
    ),
    path("api/metrics/daily/", views.metrics_daily_view, name="metrics_daily"),
    path("api/metrics/weekly/", views.metrics_weekly_view, name="metrics_weekly"),
    path("api/metrics/monthly/", views.metrics_monthly_view, name="metrics_monthly"),
    path("api/metrics/heatmap/", views.metrics_heatmap_view, name="metrics_heatmap"),
    path("api/scores/daily/", views.scores_daily_api_view, name="scores_daily"),
    path("api/scores/<str:date>/", views.score_detail_api_view, name="scores_detail"),
    path(
        "api/reflections/", views.reflections_create_api_view, name="reflections_create"
    ),
    path(
        "api/reflections/<int:pk>/",
        views.reflections_update_api_view,
        name="reflections_update",
    ),
    path(
        "api/reflections/history/",
        views.reflections_history_api_view,
        name="reflections_history",
    ),
]
