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
    # Scenario routes (Task 12)
    path("scenario/", views.scenario_view, name="scenario"),
    path("scenario/<int:event_id>/", views.scenario_view, name="scenario_event"),
    path("api/events/<int:event_id>/rounds/", views.event_rounds_api, name="api_event_rounds"),
    path("api/events/<int:event_id>/rounds/reorder/", views.event_rounds_reorder_api, name="api_event_rounds_reorder"),
    path("api/rounds/<int:round_id>/", views.round_detail_api, name="api_round_detail"),
    # Theme & Prize routes (Task 15)
    path("theme/", views.theme_editor_view, name="theme"),
    path("theme/<int:theme_id>/", views.theme_editor_view, name="theme_detail"),
    path("api/themes/<int:theme_id>/", views.api_theme_detail, name="api_theme_detail"),
]
