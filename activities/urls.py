from django.urls import path

from activities import views

urlpatterns = [
    path("categories/", views.category_list_view, name="category_list"),
    path("categories/new/", views.category_create_view, name="category_create"),
    path(
        "categories/<int:pk>/edit/",
        views.category_update_view,
        name="category_update",
    ),
    path(
        "categories/<int:pk>/delete/",
        views.category_delete_view,
        name="category_delete",
    ),
    path("", views.activity_list_view, name="activity_list"),
    path("new/", views.activity_create_view, name="activity_create"),
    path("<int:pk>/", views.activity_detail_view, name="activity_detail"),
    path("<int:pk>/edit/", views.activity_update_view, name="activity_update"),
    path("<int:pk>/delete/", views.activity_delete_view, name="activity_delete"),
    path(
        "<int:activity_id>/recurrence/",
        views.recurrence_edit_view,
        name="recurrence_edit",
    ),
    path(
        "<int:pk>/toggle/",
        views.activity_toggle_active_view,
        name="activity_toggle",
    ),
    path(
        "<int:pk>/quick-target/",
        views.activity_quick_target_view,
        name="activity_quick_target",
    ),
]
