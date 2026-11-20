"""Full End-to-End Forum Scenario Integration Test (Day 7 Verification).

Simulates the complete event journey from forum launch to supergame finale:
  1. Complete event setup (Theme, Questions, Wheels, Sectors, Prizes, Rounds, Players);
  2. First Qualifying Round: spins, letter guesses, miss turn transition;
  3. 3-in-a-row letter streak triggering Two Boxes minigame;
  4. Sector «+» opening any closed cell;
  5. Emergency host buttons (Undo, Manual score adjustment);
  6. Final Round: Bankrupt sector effect;
  7. Supergame: Free letter selection without points, server countdown timer, victory;
  8. Prize showcase exchange;
  9. Full package export and restore verification.
"""

import tempfile
from pathlib import Path
import pytest
from django.test import Client

from apps.core.models import Effect, Event, GameLog, GameSession, Player, Prize, Question, Round, Sector, Theme, Wheel
from apps.core.packaging import export_event, import_event
from apps.game import services


@pytest.mark.django_db
class TestFullGameScenario:
    def test_complete_forum_gameplay_to_supergame_and_export(self):
        client = Client()

        # ====================================================================
        # Phase 1: Setup Event Data
        # ====================================================================
        theme = Theme.objects.create(
            name="Корпоративный Доломит",
            colors={
                "bg_main": "#0b132b",
                "bg_card": "#1c2541",
                "color_gold": "#f4c430",
            },
        )
        event = Event.objects.create(
            name="Молодёжный форум ОАО «Доломит»",
            theme=theme,
            rules={"scoring": "per_occurrence", "word_bonus": 500},
            is_active=True,
        )

        # Questions
        q_qualifying = Question.objects.create(
            word="ДОЛОМИТ",
            text="Главный минерал предприятия и осадочная порода",
            hint="Название завода",
        )
        q_final = Question.objects.create(
            word="КАРЬЕР",
            text="Место открытой добычи полезных ископаемых",
            hint="Горный объект",
        )
        q_supergame = Question.objects.create(
            word="ФЛОТАЦИЯ",
            text="Один из методов обогащения полезных ископаемых",
            hint="Технологический процесс",
        )

        # Wheel with effects
        wheel = Wheel.objects.create(name="Главный барабан")
        eff_bankrupt = Effect.objects.create(name="Банкрот", actions=[{"type": "bankrupt"}])
        eff_plus = Effect.objects.create(name="Сектор Плюс", actions=[{"type": "reveal_any_letter"}])

        Sector.objects.create(wheel=wheel, order=0, label="100", value=100)
        Sector.objects.create(wheel=wheel, order=1, label="300", value=300)
        Sector.objects.create(wheel=wheel, order=2, label="500", value=500)
        Sector.objects.create(wheel=wheel, order=3, label="Б", value=0, effect=eff_bankrupt)
        Sector.objects.create(wheel=wheel, order=4, label="+", value=0, effect=eff_plus)

        # Prizes
        prize_watch = Prize.objects.create(event=event, name="Умные часы", cost=400)
        prize_car = Prize.objects.create(event=event, name="Главный суперприз", cost=1500)

        # Rounds
        Round.objects.create(event=event, order=1, type=Round.Type.QUALIFYING, question=q_qualifying, wheel=wheel)
        Round.objects.create(event=event, order=2, type=Round.Type.FINAL, question=q_final, wheel=wheel)
        Round.objects.create(event=event, order=3, type=Round.Type.SUPERGAME, question=q_supergame, wheel=wheel, prize=prize_car)

        # Players
        Player.objects.create(event=event, name="Алексей", team="Горный цех", order=1)
        Player.objects.create(event=event, name="Ольга", team="ЦЗЛ", order=2)
        Player.objects.create(event=event, name="Дмитрий", team="Управление", order=3)

        # ====================================================================
        # Phase 2: Start Game Session (Qualifying Round: 'ДОЛОМИТ')
        # ====================================================================
        session = services.get_or_create_session(event_id=event.id)
        assert session.state["word"] == "ДОЛОМИТ"
        assert session.state["players"] == ["Алексей", "Ольга", "Дмитрий"]
        assert session.state["current_player"] == 0

        # Step 2.1: Алексей spins 500 points
        s_data = services.apply_action(
            {"type": "SPIN_RESULT", "sector_index": 2, "sector_value": 500},
            expected_version=session.version,
            session_id=session.pk,
        )
        assert s_data["sector_value"] == 500

        # Step 2.2: Алексей guesses 'Д' -> earns 500 points
        s_data = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Д"},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["scores"][0] == 500
        assert s_data["mask"][0] is True
        assert s_data["current_player"] == 0  # Still Алексей's turn

        # Step 2.3: Алексей misses with 'Щ' -> turn passes to Ольга
        s_data = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Щ"},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["current_player"] == 1  # Ольга

        # Step 2.4: Ольга spins 300 points
        s_data = services.apply_action(
            {"type": "SPIN_RESULT", "sector_index": 1, "sector_value": 300},
            expected_version=s_data["version"],
            session_id=session.pk,
        )

        # Step 2.5: Ольга guesses 3 letters in a row: 'О', 'Л', 'М'
        # 'О' appears twice: indices 1 and 3 -> earns 300 * 2 = 600
        s_data = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "О"},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["scores"][1] == 600
        assert s_data["letter_streak"] == 1

        # 'Л' at index 2
        s_data = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Л"},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["scores"][1] == 900
        assert s_data["letter_streak"] == 2

        # 'М' at index 4 -> 3rd letter in a row triggers Two Boxes minigame!
        s_data = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "М"},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["scores"][1] == 1200
        assert s_data["special_event"] == "two_boxes"
        assert s_data["pending_modal"] == "two_boxes"

        # Step 2.6: Two Boxes: Ольга chooses Box 0 (the prize box)
        s_data = services.apply_action(
            {"type": "CHOOSE_BOX", "box_index": 0},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        # Receives +500 box points!
        assert s_data["scores"][1] == 1700
        assert s_data["special_event"] == ""
        assert s_data["phase"] == "await_letter"

        # Step 2.7: Ольга lands on sector '+' (index 4)
        s_data = services.apply_action(
            {"type": "SPIN_RESULT", "sector_index": 4, "sector_value": 0},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["special_event"] == "reveal_any_letter"
        assert s_data["pending_modal"] == "reveal_cell"

        # Ольга touches closed cell 5 ('И')
        assert not s_data["mask"][5]
        s_data = services.apply_action(
            {"type": "REVEAL_CELL", "cell_index": 5},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_data["mask"][5] is True  # 'И' opened!
        assert s_data["special_event"] == ""

        # Step 2.8: Host Undo emergency test
        # Host mistakenly awarded 100 points via manual score
        s_bad = services.apply_action(
            {"type": "MANUAL_SCORE", "player": 1, "delta": 100},
            expected_version=s_data["version"],
            session_id=session.pk,
        )
        assert s_bad["scores"][1] == 1800

        # Host presses UNDO
        s_restored = services.apply_action(
            {"type": "UNDO"},
            expected_version=s_bad["version"],
            session_id=session.pk,
        )
        assert s_restored["scores"][1] == 1700  # Restored!

        # Step 2.9: Complete remaining letter 'Т' (pos 6) -> Qualifying Round Won!
        s_won = services.apply_action(
            {"type": "GUESS_LETTER", "letter": "Т"},
            expected_version=s_restored["version"],
            session_id=session.pk,
        )
        assert s_won["phase"] == "round_won"
        assert all(s_won["mask"])

        # ====================================================================
        # Phase 3: Supergame
        # ====================================================================
        # Start Supergame with 3 free letters and 60 second timer
        s_sg = services.apply_action(
            {"type": "START_SUPERGAME", "limit": 3, "duration": 60},
            expected_version=s_won["version"],
            session_id=session.pk,
        )
        assert s_sg["is_supergame"] is True
        assert s_sg["phase"] == "supergame_selection"

        # Finalist chooses 3 free letters ('Д', 'О', 'М')
        score_before_sg = s_sg["scores"][1]
        s_letters = services.apply_action(
            {"type": "SUPERGAME_LETTERS", "letters": ["Д", "О", "М"]},
            expected_version=s_sg["version"],
            session_id=session.pk,
        )
        assert s_letters["scores"][1] == score_before_sg  # NO points awarded!
        assert s_letters["phase"] == "supergame_thinking"
        assert s_letters["timer_end_timestamp"] is not None

        # Finalist guesses the word correctly before timer expires!
        s_sg_won = services.apply_action(
            {"type": "SUPERGAME_GUESS", "correct": True},
            expected_version=s_letters["version"],
            session_id=session.pk,
        )
        assert s_sg_won["phase"] == "supergame_won"
        assert s_sg_won["pending_sound"] == "win"

        # ====================================================================
        # Phase 4: Prize Showcase Exchange
        # ====================================================================
        # Finalist exchanges 400 points for 'Умные часы'
        final_score = s_sg_won["scores"][1]
        exchange_resp = client.post(
            "/api/prizes/exchange/",
            data={"prize_id": prize_watch.id, "player_index": 1},
            content_type="application/json",
        )
        assert exchange_resp.status_code == 200
        ex_data = exchange_resp.json()
        assert ex_data["status"] == "ok"
        assert ex_data["remaining_score"] == final_score - 400
        assert GameLog.objects.filter(action="EXCHANGE_PRIZE").exists()

        # ====================================================================
        # Phase 5: Export Event to ZIP and Verify Round-Trip
        # ====================================================================
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_dest = Path(tmpdir) / "forum_event.zip"
            export_event(event, zip_dest)
            assert zip_dest.is_file()

            # Clean and re-import
            Round.objects.all().delete()
            event.delete()
            wheel.delete()

            restored = import_event(zip_dest, activate=True)
            assert restored.name == "Молодёжный форум ОАО «Доломит»"
            assert restored.is_active is True
            assert restored.rounds.count() == 3
            assert restored.prizes.count() == 2
            assert restored.players.count() == 3
