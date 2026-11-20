from django.urls import path

from apps.game import views

app_name = "game"

urlpatterns = [
    path("api/state/", views.state_api, name="state"),
    path("api/action/", views.action_api, name="action"),
]
