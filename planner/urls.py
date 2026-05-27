from django.urls import path

from planner import views

urlpatterns = [
    path("", views.daily_plan_view, name="planner_day"),
    path("create/", views.schedule_block_create_view, name="schedule_create"),
    path("<int:pk>/delete/", views.schedule_block_delete_view, name="schedule_delete"),
    path("<int:pk>/start/", views.schedule_block_start_timer_view, name="schedule_start_timer"),
    path("<int:pk>/pause/", views.schedule_block_pause_timer_view, name="schedule_pause_timer"),
    path("<int:pk>/resume/", views.schedule_block_resume_timer_view, name="schedule_resume_timer"),
    path("<int:pk>/stop/", views.schedule_block_stop_timer_view, name="schedule_stop_timer"),
    path("categories/create/", views.planner_category_create_view, name="planner_category_create"),
    path("categories/<int:pk>/update/", views.planner_category_update_view, name="planner_category_update"),
    path("categories/<int:pk>/delete/", views.planner_category_delete_view, name="planner_category_delete"),
    path("activities/create/", views.planner_activity_create_view, name="planner_activity_create"),
    path("activities/<int:pk>/update/", views.planner_activity_update_view, name="planner_activity_update"),
    path("activities/<int:pk>/delete/", views.planner_activity_delete_view, name="planner_activity_delete"),
]
