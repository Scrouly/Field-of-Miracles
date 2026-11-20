from django.urls import path

from apps.game import views

app_name = "game"

urlpatterns = [
    path("display/", views.display_view, name="display"),
    path("host/", views.host_view, name="host"),
    path("api/state/", views.state_api, name="state"),
    path("api/action/", views.action_api, name="action"),
    path("api/logs/", views.logs_api, name="logs"),
    path("api/theme/css/", views.theme_css_view, name="theme_css"),
    path("api/prizes/showcase/", views.prize_showcase_api, name="prize_showcase"),
    path("api/prizes/exchange/", views.prize_exchange_api, name="prize_exchange"),
    path("api/rounds/", views.game_rounds_api, name="game_rounds"),
    path("api/test/reset/", views.reset_test_game_api, name="test_reset"),
]
