"""Tests for Theme Editor, Sound Triggers, and Prize Showcase (Task 15)."""

import json
import pytest
from django.test import Client

from apps.core.models import Event, GameLog, GameSession, Prize, Theme
from apps.studio import theme_editor


@pytest.mark.django_db
class TestThemeEditorCore:
    def test_default_theme_creation_and_css_generation(self):
        theme = theme_editor.get_or_create_default_theme()
        assert theme.name == "Доломит — Классическая"
        assert "bg_main" in theme.colors

        css = theme_editor.generate_theme_css(theme)
        assert ":root {" in css
        assert "--bg-main: #0b132b;" in css
        assert "--color-gold: #f4c430;" in css

    def test_update_theme_colors_with_validation(self):
        theme = theme_editor.get_or_create_default_theme()
        theme_editor.update_theme_colors(
            theme,
            {
                "bg_main": "#123456",
                "color_gold": "#abcdef",
                "invalid_color": "not-a-hex",
            },
        )
        theme.refresh_from_db()
        assert theme.colors["bg_main"] == "#123456"
        assert theme.colors["color_gold"] == "#abcdef"
        assert "invalid_color" not in theme.colors

    def test_prize_showcase_calculation(self):
        event = Event.objects.create(name="Мероприятие с призами")
        p1 = Prize.objects.create(event=event, name="Кружка", cost=200)
        p2 = Prize.objects.create(event=event, name="Флешка", cost=500)
        p3 = Prize.objects.create(event=event, name="Пылесос", cost=1500)

        # Player with 500 points
        showcase = theme_editor.get_prize_showcase(event, player_score=500)
        assert showcase["player_score"] == 500
        assert showcase["total_prizes"] == 3
        assert showcase["affordable_count"] == 2

        items = showcase["prizes"]
        assert items[0]["name"] == "Кружка"
        assert items[0]["can_afford"] is True
        assert items[0]["missing_points"] == 0

        assert items[1]["name"] == "Флешка"
        assert items[1]["can_afford"] is True
        assert items[1]["missing_points"] == 0

        assert items[2]["name"] == "Пылесос"
        assert items[2]["can_afford"] is False
        assert items[2]["missing_points"] == 1000

    def test_exchange_prize_success_and_failure(self):
        event = Event.objects.create(name="Событие")
        prize = Prize.objects.create(event=event, name="Чайник", cost=400)
        session = GameSession.objects.create(
            event=event,
            version=1,
            state={
                "players": ["Игрок 1"],
                "current_player": 0,
                "scores": [500],
            },
        )

        # 1. Successful exchange
        res = theme_editor.exchange_prize(session, prize, player_index=0)
        assert res["status"] == "ok"
        assert res["remaining_score"] == 100
        assert res["version"] == 2

        session.refresh_from_db()
        assert session.state["scores"][0] == 100
        assert session.version == 2
        assert GameLog.objects.filter(action="EXCHANGE_PRIZE").exists()

        # 2. Insufficient points for second exchange
        with pytest.raises(ValueError) as exc:
            theme_editor.exchange_prize(session, prize, player_index=0)
        assert "Недостаточно очков" in str(exc.value)


@pytest.mark.django_db
class TestThemeAndPrizeAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = Client()
        self.theme = theme_editor.get_or_create_default_theme()
        self.event = Event.objects.create(name="Событие", theme=self.theme, is_active=True)
        self.prize = Prize.objects.create(event=self.event, name="Плед", cost=300)
        self.session = GameSession.objects.create(
            event=self.event,
            version=1,
            state={"players": ["Игрок"], "current_player": 0, "scores": [600]},
        )
        session = self.client.session
        session["studio_authenticated"] = True
        session.save()

    def test_dynamic_theme_css_endpoint(self):
        """Смена темы в админке видна на экране через /api/theme/css/ без правки кода."""
        resp = self.client.get("/api/theme/css/")
        assert resp.status_code == 200
        assert resp["Content-Type"] == "text/css"
        css_text = resp.content.decode("utf-8")
        assert "--bg-main:" in css_text

        # Update theme colors in DB
        self.theme.colors["bg_main"] = "#334455"
        self.theme.save()

        resp2 = self.client.get("/api/theme/css/")
        assert "--bg-main: #334455;" in resp2.content.decode("utf-8")

    def test_prize_showcase_api(self):
        resp = self.client.get("/api/prizes/showcase/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["player_score"] == 600
        assert data["affordable_count"] == 1

    def test_prize_exchange_api(self):
        resp = self.client.post(
            "/api/prizes/exchange/",
            data=json.dumps({"prize_id": self.prize.id, "player_index": 0}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["remaining_score"] == 300

    def test_studio_theme_editor_html_and_api(self):
        resp = self.client.get("/studio/theme/")
        assert resp.status_code == 200
        assert "Цвета оформления" in resp.content.decode("utf-8")

        # Update via studio API
        resp_api = self.client.post(
            f"/studio/api/themes/{self.theme.id}/",
            data=json.dumps({"colors": {"bg_main": "#112233"}}),
            content_type="application/json",
        )
        assert resp_api.status_code == 200
        self.theme.refresh_from_db()
        assert self.theme.colors["bg_main"] == "#112233"
