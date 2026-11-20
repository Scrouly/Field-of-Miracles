"""Tests for Crash Recovery, GameLog Journaling, and Undo (Task 16)."""

import json
import pytest
from django.db import connection
from django.test import Client

from apps.core.models import Effect, Event, GameLog, GameSession, Question, Round, Sector, Wheel
from apps.game import services


@pytest.mark.django_db
class TestCrashRecoveryAndUndo:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = Client()
        self.event = Event.objects.create(name="Мероприятие для теста восстановления", is_active=True)
        self.q = Question.objects.create(word="ДОЛОМИТ", text="Минерал ОАО «Доломит»")
        self.wheel = Wheel.objects.create(name="Барабан 1")

        # Effect: bankrupt
        self.eff_bankrupt = Effect.objects.create(
            name="Банкрот",
            actions=[{"type": "bankrupt"}],
        )
        self.sec0 = Sector.objects.create(wheel=self.wheel, order=0, label="100", value=100)
        self.sec1 = Sector.objects.create(wheel=self.wheel, order=1, label="500", value=500)
        self.sec_b = Sector.objects.create(
            wheel=self.wheel, order=2, label="Б", value=0, effect=self.eff_bankrupt
        )

        self.round_obj = Round.objects.create(
            event=self.event,
            order=1,
            question=self.q,
            wheel=self.wheel,
        )

        self.session = services.get_or_create_session(event_id=self.event.id)

    def test_game_continues_with_same_turn_and_score_after_restart(self):
        """После перезапуска сервера игра продолжается с того же хода и счёта."""
        # 1. Player 0 spins 500
        v0 = self.session.version
        r_spin = services.apply_action(
            {"type": "SPIN_RESULT", "sector_index": 1, "sector_value": 500},
            expected_version=v0,
            session_id=self.session.pk,
        )
        assert r_spin["sector_value"] == 500

        # 2. Player 0 guesses 'Д' -> earns 500 points
        v1 = r_spin["version"]
        r_guess = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Д"},
            expected_version=v1,
            session_id=self.session.pk,
        )
        assert r_guess["scores"][0] == 500
        assert r_guess["mask"][0] is True
        assert r_guess["current_player"] == 0

        # Simulate hard crash & process restart by closing DB connection and clearing cache
        connection.close()

        # Re-fetch from fresh DB query
        restarted_session = GameSession.objects.get(pk=self.session.pk)
        restarted_state = services.get_state_data(session_id=restarted_session.pk)

        # State is fully preserved
        assert restarted_state["version"] == r_guess["version"]
        assert restarted_state["scores"][0] == 500
        assert restarted_state["mask"][0] is True
        assert restarted_state["current_player"] == 0
        assert restarted_state["word"] == "ДОЛОМИТ"

    def test_undo_rolls_back_single_letter_action(self):
        """Undo откатывает ровно одно действие (букву)."""
        # Guess 'Д'
        v0 = self.session.version
        r1 = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Д"},
            expected_version=v0,
            session_id=self.session.pk,
        )
        assert r1["mask"][0] is True
        assert r1["scores"][0] == 100
        log_count_before = GameLog.objects.filter(session=self.session).count()

        # Trigger UNDO
        v1 = r1["version"]
        r_undo = services.apply_action(
            {"type": "UNDO"},
            expected_version=v1,
            session_id=self.session.pk,
        )

        assert r_undo["mask"][0] is False  # 'Д' hidden again
        assert r_undo["scores"][0] == 0  # Score rolled back
        assert r_undo["version"] == v1 + 1  # Version bumped to invalidate clients
        assert GameLog.objects.filter(session=self.session).count() == log_count_before - 1

    def test_undo_rolls_back_wheel_spin_including_effects(self):
        """Undo откатывает результат барабана, включая банкрот."""
        # 1. Give player 0 300 points
        v0 = self.session.version
        r1 = services.apply_action(
            {"type": "MANUAL_SCORE", "player": 0, "delta": 300},
            expected_version=v0,
            session_id=self.session.pk,
        )
        assert r1["scores"][0] == 300

        # 2. Land on Bankrupt sector (sector_index 2)
        v1 = r1["version"]
        r_bankrupt = services.apply_action(
            {"type": "SPIN_RESULT", "sector_index": 2, "sector_value": 0},
            expected_version=v1,
            session_id=self.session.pk,
        )
        assert r_bankrupt["scores"][0] == 0
        assert r_bankrupt["current_player"] == 1  # Turn passed to player 1

        # 3. Undo the bankrupt spin!
        v2 = r_bankrupt["version"]
        r_undone = services.apply_action(
            {"type": "UNDO"},
            expected_version=v2,
            session_id=self.session.pk,
        )

        # Player 0 restored with 300 points, turn restored to player 0
        assert r_undone["scores"][0] == 300
        assert r_undone["current_player"] == 0

    def test_undo_when_no_logs_does_not_fail(self):
        """Вызов Undo в начале игры без логов не приводит к ошибке."""
        v0 = self.session.version
        res = services.apply_action(
            {"type": "UNDO"},
            expected_version=v0,
            session_id=self.session.pk,
        )
        assert res["status"] == "ok"
        assert res["changed"] is False

    def test_undo_after_load_round_does_not_crash(self):
        """Undo после переключения тура корректно откатывает действие в новом туре."""
        q2 = Question.objects.create(word="КАРЬЕР", text="Вопрос 2")
        r2 = Round.objects.create(
            event=self.event,
            order=2,
            question=q2,
            wheel=self.wheel,
            params={"players": ["Игрок А", "Игрок Б", "Игрок В"]},
        )
        # Load round 2
        v0 = self.session.version
        services.apply_action(
            {"type": "LOAD_ROUND", "round_id": r2.pk},
            expected_version=v0,
            session_id=self.session.pk,
        )

        # Guess letter 'К' in round 2
        s = GameSession.objects.get(pk=self.session.pk)
        r_guess = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "к"},
            expected_version=s.version,
            session_id=self.session.pk,
        )
        assert r_guess["word"] == "КАРЬЕР"
        assert r_guess["mask"][0] is True

        # Call Undo
        r_undo = services.apply_action(
            {"type": "UNDO"},
            expected_version=r_guess["version"],
            session_id=self.session.pk,
        )
        assert r_undo["word"] == "КАРЬЕР"
        assert r_undo["mask"][0] is False
