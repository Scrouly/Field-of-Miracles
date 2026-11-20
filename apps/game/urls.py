from django.urls import path

from apps.game import views

app_name = "game"

urlpatterns = [
    path("display/", views.display_view, name="display"),
    path("host/", views.host_view, name="host"),
    path("api/state/", views.state_api, name="state"),
    path("api/action/", views.action_api, name="action"),
    path("api/logs/", views.logs_api, name="logs"),
]
