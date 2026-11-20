"""URL routing for apps.studio."""

from django.urls import path

from . import views

app_name = "studio"

urlpatterns = [
    path("", views.wheel_editor_view, name="index"),
    path("login/", views.studio_login_view, name="login"),
    path("logout/", views.studio_logout_view, name="logout"),
    path("wheels/", views.wheel_editor_view, name="wheels"),
    path("wheels/<int:wheel_id>/", views.wheel_editor_view, name="wheel_detail"),
    path("api/wheels/", views.wheel_list_api, name="api_wheels"),
    path("api/wheels/<int:wheel_id>/", views.wheel_detail_api, name="api_wheel_detail"),
    path("api/wheels/<int:wheel_id>/sectors/", views.wheel_sectors_api, name="api_wheel_sectors"),
]
