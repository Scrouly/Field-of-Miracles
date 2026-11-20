"""Tests for the game state and action API (Task 4).

Covers:
  1. Stale expected_version is rejected (HTTP 409 Conflict).
  2. Each applied action creates an entry in GameLog with sequential numbering.
  3. GET /api/state/?since=<version> returns 'без новостей' when unchanged.
  4. Concurrent actions from two devices: second action is rejected, state is safe.
  5. Invalid actions / missing expected_version return HTTP 400.
"""

from __future__ import annotations

import json
import pytest
from django.test import Client

from apps.core.models import GameLog, GameSession
from engine.state import new_game, state_to_dict
from tests.factories import EventFactory, GameSessionFactory, PlayerFactory, QuestionFactory, RoundFactory


@pytest.fixture()
def active_game(db: None) -> GameSession:
    """Fixture providing an active GameSession with 'ДОЛОМИТ' and 3 players."""
    event = EventFactory(is_active=True, rules={"scoring": "per_occurrence", "word_bonus": 500})
    PlayerFactory(event=event, name="Анна", order=1)
    PlayerFactory(event=event, name="Борис", order=2)
    PlayerFactory(event=event, name="Вера", order=3)

    question = QuestionFactory(word="ДОЛОМИТ", text="Минерал и предприятие", hint="Горная порода")
    RoundFactory(event=event, order=1, question=question)

    init_state = new_game(
        word="ДОЛОМИТ",
        players=["Анна", "Борис", "Вера"],
        scoring="per_occurrence",
        word_bonus=500,
        sector_value=100,
        question="Минерал и предприятие",
        hint="Горная порода",
    )
    return GameSessionFactory(
        event=event,
        state=state_to_dict(init_state),
        version=0,
    )


# ===================================================================
#  1. GET /api/state/
# ===================================================================


@pytest.mark.django_db
class TestGetStateApi:
    def test_get_state_initial_returns_full_state(self, client: Client, active_game: GameSession):
        resp = client.get("/api/state/")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["changed"] is True
        assert data["version"] == 0
        assert data["word"] == "ДОЛОМИТ"
        assert data["players"] == ["Анна", "Борис", "Вера"]
        assert data["current_player"] == 0
        assert data["scores"] == [0, 0, 0]
        assert data["mask"] == [False] * 7
        assert "state" in data

    def test_get_state_unchanged_answers_no_news(self, client: Client, active_game: GameSession):
        """GET без изменений отвечает «без новостей»."""
        resp = client.get(f"/api/state/?since={active_game.version}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "no_news"
        assert data["changed"] is False
        assert data["version"] == active_game.version
        assert "без новостей" in data["message"]

    def test_get_state_future_version_answers_no_news(self, client: Client, active_game: GameSession):
        resp = client.get("/api/state/?since=999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_news"
        assert data["changed"] is False

    def test_get_state_older_since_returns_state(self, client: Client, active_game: GameSession):
        # Bump session version to 2
        active_game.version = 2
        active_game.save(update_fields=["version"])

        resp = client.get("/api/state/?since=1")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["changed"] is True
        assert data["version"] == 2

    def test_get_state_by_session_id(self, client: Client, active_game: GameSession):
        resp = client.get(f"/api/state/?session_id={active_game.pk}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == active_game.pk

    def test_get_state_nonexistent_session_id_returns_404(self, client: Client, db: None):
        resp = client.get("/api/state/?session_id=99999")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"

    def test_get_state_invalid_since_param_returns_400(self, client: Client, active_game: GameSession):
        resp = client.get("/api/state/?since=abc")
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_parameter"

    def test_post_to_state_api_not_allowed(self, client: Client, active_game: GameSession):
        resp = client.post("/api/state/")
        assert resp.status_code == 405


# ===================================================================
#  2. POST /api/action/ & Optimistic Locking
# ===================================================================


@pytest.mark.django_db
class TestActionApi:
    def test_action_successful_updates_state_and_version(
        self, client: Client, active_game: GameSession
    ):
        payload = {
            "expected_version": 0,
            "action": {
                "type": "GUESS_LETTER",
                "letter": "д",
            },
        }
        resp = client.post(
            "/api/action/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "ok"
        assert data["version"] == 1
        assert data["mask"][0] is True  # 'Д' revealed
        assert data["scores"][0] == 100  # 100 points awarded

        # DB updated
        active_game.refresh_from_db()
        assert active_game.version == 1
        assert active_game.state["version"] == 1
        assert active_game.state["mask"][0] is True

    def test_action_with_stale_expected_version_rejected(
        self, client: Client, active_game: GameSession
    ):
        """Действие с устаревшим expected_version отклоняется."""
        # Bump DB version to 1
        active_game.version = 1
        active_game.save(update_fields=["version"])

        payload = {
            "expected_version": 0,  # Stale!
            "action": {
                "type": "GUESS_LETTER",
                "letter": "д",
            },
        }
        resp = client.post(
            "/api/action/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 409
        data = resp.json()

        assert data["error"] == "conflict"
        assert data["current_version"] == 1
        assert "устарела" in data["message"]

        # No changes in database
        active_game.refresh_from_db()
        assert active_game.version == 1
        assert GameLog.objects.filter(session=active_game).count() == 0

    def test_flat_action_payload_format_supported(
        self, client: Client, active_game: GameSession
    ):
        """Action fields can be sent directly at top-level."""
        payload = {
            "expected_version": 0,
            "type": "GUESS_LETTER",
            "letter": "о",
        }
        resp = client.post(
            "/api/action/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["mask"][1] is True  # First 'О'
        assert data["mask"][3] is True  # Second 'О'
        assert data["scores"][0] == 200  # 2 * 100

    def test_missing_expected_version_returns_400(
        self, client: Client, active_game: GameSession
    ):
        payload = {"action": {"type": "SKIP_TURN"}}
        resp = client.post(
            "/api/action/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "missing_expected_version"

    def test_invalid_json_returns_400(self, client: Client, active_game: GameSession):
        resp = client.post(
            "/api/action/",
            data="NOT_JSON",
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"

    def test_invalid_action_rejected_with_400(
        self, client: Client, active_game: GameSession
    ):
        payload = {
            "expected_version": 0,
            "action": {"type": "UNKNOWN_ACTION_TYPE"},
        }
        resp = client.post(
            "/api/action/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_action"

    def test_get_to_action_api_not_allowed(self, client: Client, active_game: GameSession):
        resp = client.get("/api/action/")
        assert resp.status_code == 405


# ===================================================================
#  3. GameLog Journaling
# ===================================================================


@pytest.mark.django_db
class TestGameLogJournal:
    def test_every_action_creates_gamelog_entry(
        self, client: Client, active_game: GameSession
    ):
        """Каждое действие создаёт запись в GameLog."""
        assert GameLog.objects.filter(session=active_game).count() == 0

        # Action 1: Guess letter 'д' (hit)
        resp1 = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 0,
                "action": {"type": "GUESS_LETTER", "letter": "д"},
            }),
            content_type="application/json",
        )
        assert resp1.status_code == 200

        # Action 2: Guess letter 'я' (miss -> turn passes to player 1)
        resp2 = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 1,
                "action": {"type": "GUESS_LETTER", "letter": "я"},
            }),
            content_type="application/json",
        )
        assert resp2.status_code == 200

        # Action 3: Skip turn (player 1 -> player 2)
        resp3 = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 2,
                "action": {"type": "SKIP_TURN"},
            }),
            content_type="application/json",
        )
        assert resp3.status_code == 200

        # Action 4: Manual score (+50 to player 0)
        resp4 = client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 3,
                "action": {"type": "MANUAL_SCORE", "player": 0, "delta": 50},
            }),
            content_type="application/json",
        )
        assert resp4.status_code == 200

        # Check GameLog entries
        logs = list(GameLog.objects.filter(session=active_game).order_by("number"))
        assert len(logs) == 4

        assert logs[0].number == 1
        assert logs[0].action == "GUESS_LETTER"
        assert logs[0].data["letter"] == "д"

        assert logs[1].number == 2
        assert logs[1].action == "GUESS_LETTER"
        assert logs[1].data["letter"] == "я"

        assert logs[2].number == 3
        assert logs[2].action == "SKIP_TURN"

        assert logs[3].number == 4
        assert logs[3].action == "MANUAL_SCORE"
        assert logs[3].data["player"] == 0
        assert logs[3].data["delta"] == 50

    def test_rejected_action_does_not_create_gamelog(
        self, client: Client, active_game: GameSession
    ):
        # Stale action
        client.post(
            "/api/action/",
            data=json.dumps({
                "expected_version": 999,
                "action": {"type": "SKIP_TURN"},
            }),
            content_type="application/json",
        )
        assert GameLog.objects.filter(session=active_game).count() == 0


# ===================================================================
#  4. Race Condition: Two devices submit simultaneously
# ===================================================================


@pytest.mark.django_db
class TestConcurrencyProtection:
    def test_simultaneous_actions_second_rejected_state_unspoiled(
        self, client: Client, active_game: GameSession
    ):
        """Review Focus #5:

        Два устройства меняют состояние одновременно. Ведущий и экран
        нажимают в одну секунду: второе действие отклоняется с понятным
        сообщением, состояние не портится.
        """
        # Both devices see expected_version = 0
        device_display_payload = {
            "expected_version": 0,
            "action": {"type": "GUESS_LETTER", "letter": "д"},
        }
        device_host_payload = {
            "expected_version": 0,
            "action": {"type": "GUESS_LETTER", "letter": "о"},
        }

        # Device 1 succeeds
        resp1 = client.post(
            "/api/action/",
            data=json.dumps(device_display_payload),
            content_type="application/json",
        )
        assert resp1.status_code == 200
        assert resp1.json()["version"] == 1

        # Device 2 tries with stale version 0
        resp2 = client.post(
            "/api/action/",
            data=json.dumps(device_host_payload),
            content_type="application/json",
        )
        assert resp2.status_code == 409
        err = resp2.json()
        assert err["error"] == "conflict"
        assert err["current_version"] == 1
        assert "устарела" in err["message"]

        # Only Device 1's action was logged and applied
        logs = list(GameLog.objects.filter(session=active_game))
        assert len(logs) == 1
        assert logs[0].action == "GUESS_LETTER"
        assert logs[0].data["letter"] == "д"

        # State is clean
        active_game.refresh_from_db()
        assert active_game.version == 1
        assert active_game.state["mask"][0] is True   # 'Д' open
        assert active_game.state["mask"][1] is False  # 'О' not open
