from django.urls import path

from planner import views

urlpatterns = [
    path("", views.daily_plan_view, name="planner_day"),
    path("create/", views.schedule_block_create_view, name="schedule_create"),
    path("<int:pk>/delete/", views.schedule_block_delete_view, name="schedule_delete"),
    path("<int:pk>/start/", views.schedule_block_start_timer_view, name="schedule_start_timer"),
    path("<int:pk>/stop/", views.schedule_block_stop_timer_view, name="schedule_stop_timer"),
]
