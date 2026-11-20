"""Tests for Supergame and Server Timer (Task 14)."""

import pytest

from engine.actions import (
    apply,
    start_supergame as start_supergame_act,
    supergame_guess,
    supergame_letters,
    supergame_time_up,
)
from engine.state import GameState, new_game
from engine.supergame import (
    SupergameError,
    choose_free_letters,
    is_timer_expired,
    resolve_supergame,
    start_supergame,
    time_up,
)


@pytest.fixture()
def game_state() -> GameState:
    """Round with word 'МИНЕРАЛОГИЯ' and 1 player with initial score 1500."""
    state = new_game(
        word="МИНЕРАЛОГИЯ",
        players=["Победитель Финала"],
        sector_value=100,
    )
    from dataclasses import replace
    return replace(state, scores=(1500,))


class TestSupergameCore:
    def test_start_supergame_initializes_state(self, game_state: GameState):
        state = start_supergame(game_state, free_letters_limit=3, timer_duration=60)
        assert state.is_supergame is True
        assert state.phase == "supergame_selection"
        assert state.free_letters_limit == 3
        assert state.timer_duration == 60
        assert state.timer_end_timestamp is None
        assert state.pending_modal == "supergame_selection"

    def test_choose_free_letters_reveals_letters_without_points(self, game_state: GameState):
        """Открытие 3–4 букв без очков."""
        state = start_supergame(game_state, free_letters_limit=3, timer_duration=60)
        initial_score = state.scores[0]

        # Player names letters: 'М', 'И', 'А'
        # 'МИНЕРАЛОГИЯ': contains 'М' (pos 0), 'И' (pos 1, 9), 'А' (pos 6)
        state_after = choose_free_letters(state, ["М", "И", "А"], start_time=1000.0)

        # Scores must NOT change!
        assert state_after.scores[0] == initial_score
        assert state_after.phase == "supergame_thinking"
        assert state_after.chosen_free_letters == ("м", "и", "а")
        assert state_after.mask[0] is True  # 'М'
        assert state_after.mask[1] is True  # 'И'
        assert state_after.mask[5] is True  # 'А'
        assert state_after.mask[9] is True  # 'И'
        assert state_after.mask[2] is False  # 'Н' closed

    def test_choose_free_letters_normalizes_yo(self, game_state: GameState):
        from dataclasses import replace
        yo_game = replace(game_state, word="САМОЛЁТ", mask=(False,) * 7)
        state = start_supergame(yo_game, free_letters_limit=3)

        # Choosing 'Е' opens 'Ё'
        state_after = choose_free_letters(state, ["Е"], start_time=1000.0)
        assert state_after.mask[5] is True  # 'Ё' at index 5 opened

    def test_cannot_exceed_free_letters_limit(self, game_state: GameState):
        state = start_supergame(game_state, free_letters_limit=3)
        with pytest.raises(SupergameError) as exc:
            choose_free_letters(state, ["А", "Б", "В", "Г"], start_time=1000.0)
        assert "Allowed at most 3 free letters" in str(exc.value)

    def test_server_timer_calculation(self, game_state: GameState):
        """Таймер считает по времени сервера, а не по времени вкладки."""
        state = start_supergame(game_state, timer_duration=60)
        fixed_start = 1700000000.0
        state_after = choose_free_letters(state, ["М", "И"], start_time=fixed_start)

        # Timer end must be exactly start + duration on server
        assert state_after.timer_end_timestamp == 1700000060.0

        # At 30s elapsed -> not expired
        assert is_timer_expired(state_after, current_time=1700000030.0) is False

        # At 60s elapsed -> expired!
        assert is_timer_expired(state_after, current_time=1700000060.0) is True
        assert is_timer_expired(state_after, current_time=1700000065.0) is True

    def test_time_up_triggers_gong(self, game_state: GameState):
        """По истечении времени звучит гонг и раунд переходит в supergame_lost."""
        state = start_supergame(game_state, timer_duration=30)
        state_thinking = choose_free_letters(state, ["М"], start_time=1000.0)

        lost_state = time_up(state_thinking)
        assert lost_state.phase == "supergame_lost"
        assert lost_state.pending_sound == "gong"
        assert lost_state.pending_modal == "supergame_time_up"

    def test_supergame_win(self, game_state: GameState):
        state = start_supergame(game_state)
        state_thinking = choose_free_letters(state, ["М"], start_time=1000.0)

        won_state = resolve_supergame(state_thinking, correct=True)
        assert won_state.phase == "supergame_won"
        assert all(won_state.mask)  # entire word revealed
        assert won_state.pending_sound == "win"
        assert won_state.pending_modal == "supergame_win"


class TestSupergameActionsIntegration:
    def test_apply_supergame_actions_chain(self, game_state: GameState):
        s0 = apply(game_state, start_supergame_act(limit=4, duration=30))
        assert s0.is_supergame is True
        assert s0.free_letters_limit == 4

        s1 = apply(s0, supergame_letters(["М", "И", "Н"]))
        assert s1.phase == "supergame_thinking"
        assert s1.timer_end_timestamp is not None

        s2 = apply(s1, supergame_guess(correct=True))
        assert s2.phase == "supergame_won"
        assert all(s2.mask)
