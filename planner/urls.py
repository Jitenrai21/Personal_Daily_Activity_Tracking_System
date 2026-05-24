from django.urls import path

from planner import views

urlpatterns = [
    path("", views.daily_plan_view, name="planner_day"),
    path("create/", views.schedule_block_create_view, name="schedule_create"),
    path("<int:pk>/delete/", views.schedule_block_delete_view, name="schedule_delete"),
    path("generate/", views.generate_day_view, name="schedule_generate"),
    path("routines/", views.routine_list_view, name="routine_list"),
    path("routines/create/", views.routine_create_view, name="routine_create"),
    path("routines/<int:pk>/delete/", views.routine_delete_view, name="routine_delete"),
]
