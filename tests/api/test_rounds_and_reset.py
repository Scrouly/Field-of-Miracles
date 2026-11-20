"""Tests for round switching, reset, and test game preparation."""

import pytest
from django.test import Client

from apps.core.models import Event, GameSession, Question, Round, Theme, Wheel
from apps.game import services


@pytest.mark.django_db
class TestRoundsAndReset:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        theme = Theme.objects.create(name="Тестовая тема")
        self.event = Event.objects.create(name="Тестовая игра Доломит", theme=theme, is_active=True)
        self.wheel = Wheel.objects.create(name="Тестовый барабан")

        self.q1 = Question.objects.create(word="ДОЛОМИТ", text="Вопрос 1", hint="Подсказка 1")
        self.q2 = Question.objects.create(word="КАРЬЕР", text="Вопрос 2", hint="Подсказка 2")

        self.r1 = Round.objects.create(
            event=self.event,
            order=1,
            type=Round.Type.QUALIFYING,
            question=self.q1,
            wheel=self.wheel,
            params={"players": ["Иван", "Елена", "Сергей"]},
        )
        self.r2 = Round.objects.create(
            event=self.event,
            order=2,
            type=Round.Type.QUALIFYING,
            question=self.q2,
            wheel=self.wheel,
            params={"players": ["Дмитрий", "Ольга", "Алексей"]},
        )

    def test_game_rounds_api(self, client: Client):
        response = client.get("/api/rounds/")
        assert response.status_code == 200
        data = response.json()
        assert "rounds" in data
        assert len(data["rounds"]) >= 2
        words = [r["word"] for r in data["rounds"]]
        assert "ДОЛОМИТ" in words
        assert "КАРЬЕР" in words

    def test_load_round_action(self, client: Client):
        session = services.get_or_create_session()
        assert session.state["word"] == "ДОЛОМИТ"

        # Host switches to Round 2
        response = client.post(
            "/api/action/",
            data={
                "expected_version": session.version,
                "action": {"type": "LOAD_ROUND", "round_id": self.r2.pk},
            },
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["word"] == "КАРЬЕР"
        assert data["players"] == ["Дмитрий", "Ольга", "Алексей"]
        assert data["mask"] == [False] * 6

    def test_reset_round_action(self, client: Client):
        session = services.get_or_create_session()

        # Guess letter 'Д'
        res1 = client.post(
            "/api/action/",
            data={
                "expected_version": session.version,
                "action": {"type": "GUESS_LETTER", "letter": "д"},
            },
            content_type="application/json",
        )
        assert res1.status_code == 200
        version_after_guess = res1.json()["version"]

        # Reset round
        res_reset = client.post(
            "/api/action/",
            data={
                "expected_version": version_after_guess,
                "action": {"type": "RESET_ROUND"},
            },
            content_type="application/json",
        )
        assert res_reset.status_code == 200
        data = res_reset.json()
        assert data["mask"] == [False] * 7  # All cells hidden again
        assert data["guessed_letters"] == []

    def test_reset_test_game_api(self, client: Client):
        response = client.post("/api/test/reset/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["word"] == "ДОЛОМИТ"
        assert len(data["players"]) == 3
