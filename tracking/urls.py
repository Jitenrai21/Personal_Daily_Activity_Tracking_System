from django.urls import path

from tracking import views

urlpatterns = [
    path("", views.session_list_view, name="session_list"),
    path("start/", views.session_start_view, name="session_start"),
    path("stop/", views.session_stop_view, name="session_stop"),
    path("log/", views.session_log_view, name="session_log"),
    path("export/csv/", views.session_export_csv_view, name="session_export_csv"),
    path("export/json/", views.session_export_json_view, name="session_export_json"),
    path("<int:pk>/", views.session_detail_view, name="session_detail"),
    path("<int:pk>/edit/", views.session_update_view, name="session_update"),
    path("<int:pk>/delete/", views.session_delete_view, name="session_delete"),
]
