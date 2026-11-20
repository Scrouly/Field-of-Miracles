"""Tests for the host control panel /host/ (Task 6).

Covers:
  1. PIN protection on /host/ (login prompt, correct PIN sets session, bad PIN shows error).
  2. Authenticated host view contains secret word, question, hint, controls, and journal container.
  3. Static assets exist (host.js, host.css).
  4. Actions from host panel: skip_turn, manual_score, guess_letter, guess_word.
  5. Undo action rolls back the previous state and increments version.
  6. Action synchronization: action on /host/ is immediately visible to /display/ polling.
  7. /api/logs/ returns recent GameLog entries.
"""

from __future__ import annotations

import json
import pytest
from django.conf import settings
from django.test import Client

from apps.core.models import GameLog, GameSession
from engine.state import new_game, state_to_dict
from tests.factories import EventFactory, GameSessionFactory, PlayerFactory, QuestionFactory, RoundFactory


@pytest.fixture()
def host_game(db: None) -> GameSession:
    event = EventFactory(name="Молодёжный форум ОАО Доломит", is_active=True)
    PlayerFactory(event=event, name="Анна", order=1)
    PlayerFactory(event=event, name="Борис", order=2)
    PlayerFactory(event=event, name="Вера", order=3)

    q = QuestionFactory(word="ДОЛОМИТ", text="Главный минерал Рубы", hint="Осадочная горная порода")
    RoundFactory(event=event, order=1, question=q)

    init_state = new_game(
        word="ДОЛОМИТ",
        players=["Анна", "Борис", "Вера"],
        scoring="per_occurrence",
        word_bonus=500,
        sector_value=100,
        question="Главный минерал Рубы",
        hint="Осадочная горная порода",
    )
    return GameSessionFactory(
        event=event,
        state=state_to_dict(init_state),
        version=0,
    )


@pytest.mark.django_db
class TestHostPinAuthentication:
    def test_unauthenticated_request_shows_login_page(self, client: Client, host_game: GameSession):
        resp = client.get("/host/")
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")
        assert "PIN-код" in html
        assert 'name="pin"' in html

    def test_incorrect_pin_shows_error(self, client: Client, host_game: GameSession):
        resp = client.post("/host/", data={"pin": "0000"})
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")
        assert "Неверный PIN-код" in html
        assert not client.session.get("host_authenticated")

    def test_correct_pin_grants_access(self, client: Client, host_game: GameSession):
        resp = client.post("/host/", data={"pin": "1931"})
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")
        assert "Пульт ведущего" in html
        assert client.session.get("host_authenticated") is True

    def test_pin_via_query_param_grants_access(self, client: Client, host_game: GameSession):
        resp = client.get("/host/?pin=1931")
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")
        assert "Пульт ведущего" in html
        assert client.session.get("host_authenticated") is True


@pytest.mark.django_db
class TestHostPanelContent:
    @pytest.fixture(autouse=True)
    def authenticate_host(self, client: Client):
        s = client.session
        s["host_authenticated"] = True
        s.save()

    def test_host_panel_has_required_elements(self, client: Client, host_game: GameSession):
        resp = client.get("/host/")
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")

        # Word, question, hint, players, logs
        assert 'id="host-word-display"' in html
        assert 'id="host-question"' in html
        assert 'id="host-hint"' in html
        assert 'id="host-players"' in html
        assert 'id="host-log-list"' in html

        # Buttons
        assert 'id="btn-skip-turn"' in html
        assert 'id="btn-word-correct"' in html
        assert 'id="btn-word-incorrect"' in html
        assert 'id="btn-undo"' in html
        assert 'id="host-letter-input"' in html
        assert 'id="btn-send-letter"' in html

    def test_host_static_files_exist(self):
        static_dir = settings.BASE_DIR / "static" / "host"
        assert (static_dir / "host.js").exists()
        assert (static_dir / "host.css").exists()


@pytest.mark.django_db
class TestHostActionsAndSync:
    @pytest.fixture(autouse=True)
    def authenticate_host(self, client: Client):
        s = client.session
        s["host_authenticated"] = True
        s.save()

    def test_host_skip_turn_syncs_to_display_state(
        self, client: Client, host_game: GameSession
    ):
        """Готово, когда: действие на пульте видно на /display/ не позже чем через 1 сек."""
        # Initial display poll
        disp_init = client.get("/api/state/")
        assert disp_init.json()["version"] == 0
        assert disp_init.json()["current_player"] == 0

        # Host executes skip turn
        resp = client.post(
            "/api/action/",
            data=json.dumps({"expected_version": 0, "action": {"type": "SKIP_TURN"}}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 1

        # Next display poll (?since=0) immediately receives updated state with version 1
        disp_next = client.get("/api/state/?since=0")
        assert disp_next.status_code == 200
        data = disp_next.json()
        assert data["changed"] is True
        assert data["version"] == 1
        assert data["current_player"] == 1

    def test_host_manual_score_adjustment(
        self, client: Client, host_game: GameSession
    ):
        resp = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 0,
                "action": {"type": "MANUAL_SCORE", "player": 0, "delta": 150},
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json()["scores"][0] == 150

    def test_host_undo_reverts_action(
        self, client: Client, host_game: GameSession
    ):
        # Action 1: Player 0 guesses 'д'
        client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 0,
                "action": {"type": "GUESS_LETTER", "letter": "д"},
            }),
            content_type="application/json",
        )
        host_game.refresh_from_db()
        assert host_game.version == 1
        assert host_game.state["mask"][0] is True
        assert host_game.state["scores"][0] == 100

        # Host presses Undo
        undo_resp = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 1,
                "action": {"type": "UNDO"},
            }),
            content_type="application/json",
        )
        assert undo_resp.status_code == 200
        data = undo_resp.json()
        assert data["version"] == 2
        # 'Д' is hidden again
        assert data["mask"][0] is False
        assert data["scores"][0] == 0
        assert GameLog.objects.filter(session=host_game).count() == 0

    def test_logs_api_returns_entries(
        self, client: Client, host_game: GameSession
    ):
        # Execute an action
        client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 0,
                "action": {"type": "GUESS_LETTER", "letter": "д"},
            }),
            content_type="application/json",
        )

        resp = client.get(f"/api/logs/?session_id={host_game.pk}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["logs"]) == 1
        assert data["logs"][0]["action"] == "GUESS_LETTER"
        assert data["logs"][0]["number"] == 1
