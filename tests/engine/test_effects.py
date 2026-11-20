"""Tests for the effects engine (Task 8).

Covers:
  1. 'bankrupt' zeros the current player's score and advances turn.
  2. 'multiply' multiplies sector points and multiplier factor.
  3. Unknown action type raises UnknownEffectAction with a clear, helpful error message.
  4. 'skip_turn', 'add_points', 'reveal_any_letter', 'start_box_game', 'show_modal', 'play_sound', 'give_prize'.
  5. Compound effect executing multiple actions sequentially.
  6. Supports Effect-like objects (with .actions), dicts, lists, and strings.
"""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from engine.effects import UnknownEffectAction, run_effect
from engine.state import GameState, new_game


@pytest.fixture()
def game_state() -> GameState:
    """Fixture with 3 players, player 0 has 500 points, sector_value 100."""
    state = new_game(
        word="ДОЛОМИТ",
        players=["Анна", "Борис", "Вера"],
        sector_value=100,
    )
    # Set initial scores: Анна=500, Борис=300, Вера=100
    from dataclasses import replace
    return replace(state, scores=(500, 300, 100), current_player=0)


class TestBankruptEffect:
    def test_bankrupt_zeros_current_player_and_passes_turn(self, game_state: GameState):
        """«Банкрот» обнуляет очки игрока и передаёт ход."""
        new_state = run_effect(game_state, "bankrupt")

        # Player 0 score is zeroed, others untouched
        assert new_state.scores == (0, 300, 100)
        # Turn passed to player 1
        assert new_state.current_player == 1
        assert new_state.version == game_state.version + 1
        assert new_state.pending_sound == "bankrupt"

    def test_bankrupt_wraps_turn_to_player_zero(self, game_state: GameState):
        from dataclasses import replace
        last_player_state = replace(game_state, current_player=2)
        new_state = run_effect(last_player_state, "bankrupt")

        assert new_state.scores == (500, 300, 0)
        assert new_state.current_player == 0


class TestMultiplyEffect:
    def test_multiply_multiplies_sector_points(self, game_state: GameState):
        """multiply умножает очки за букву."""
        effect = {"type": "multiply", "factor": 2}
        new_state = run_effect(game_state, effect)

        assert new_state.sector_value == 200  # 100 * 2
        assert new_state.multiplier == 2
        assert new_state.version == game_state.version + 1

    def test_multiply_default_factor_is_two(self, game_state: GameState):
        new_state = run_effect(game_state, "multiply")
        assert new_state.sector_value == 200
        assert new_state.multiplier == 2

    def test_multiply_custom_factor(self, game_state: GameState):
        effect = {"type": "multiply", "factor": 3}
        new_state = run_effect(game_state, effect)
        assert new_state.sector_value == 300
        assert new_state.multiplier == 3


class TestUnknownEffectAction:
    def test_unknown_action_type_raises_clear_error(self, game_state: GameState):
        """Неизвестный тип действия вызывает понятную ошибку, а не падение."""
        with pytest.raises(UnknownEffectAction) as exc_info:
            run_effect(game_state, "teleport_to_mars")

        err_msg = str(exc_info.value)
        assert "teleport_to_mars" in err_msg
        assert "Неизвестный тип действия эффекта" in err_msg
        assert "bankrupt" in err_msg

    def test_unknown_action_in_dict_raises_clear_error(self, game_state: GameState):
        with pytest.raises(UnknownEffectAction):
            run_effect(game_state, {"type": "NON_EXISTING_EFFECT"})


class TestOtherStandardEffects:
    def test_skip_turn_passes_turn_without_losing_score(self, game_state: GameState):
        new_state = run_effect(game_state, "skip_turn")
        assert new_state.current_player == 1
        assert new_state.scores == (500, 300, 100)  # scores unchanged

    def test_add_points_increases_current_player_score(self, game_state: GameState):
        new_state = run_effect(game_state, {"type": "add_points", "amount": 250})
        assert new_state.scores == (750, 300, 100)
        assert new_state.current_player == 0  # does not pass turn

    def test_reveal_any_letter_triggers_special_event(self, game_state: GameState):
        new_state = run_effect(game_state, "reveal_any_letter")
        assert new_state.phase == "special_event"
        assert new_state.special_event == "reveal_any_letter"

    def test_start_box_game_triggers_special_event(self, game_state: GameState):
        new_state = run_effect(game_state, "start_box_game")
        assert new_state.phase == "special_event"
        assert new_state.special_event == "two_boxes"
        assert new_state.pending_modal == "two_boxes"

    def test_show_modal_sets_modal_name(self, game_state: GameState):
        new_state = run_effect(game_state, {"type": "show_modal", "modal": "prize_dialog"})
        assert new_state.pending_modal == "prize_dialog"
        assert new_state.phase == "special_event"

    def test_play_sound_sets_trigger(self, game_state: GameState):
        new_state = run_effect(game_state, {"type": "play_sound", "trigger": "hit"})
        assert new_state.pending_sound == "hit"

    def test_give_prize(self, game_state: GameState):
        new_state = run_effect(game_state, {"type": "give_prize", "prize": "Автомобиль"})
        assert "Автомобиль" in new_state.pending_modal


class TestCompoundAndStructuredEffects:
    def test_compound_effect_executes_in_order(self, game_state: GameState):
        compound = [
            {"type": "add_points", "amount": 200},
            {"type": "play_sound", "trigger": "bonus"},
        ]
        new_state = run_effect(game_state, compound)
        assert new_state.scores == (700, 300, 100)
        assert new_state.pending_sound == "bonus"
        # 2 actions = 2 version increments
        assert new_state.version == game_state.version + 2

    def test_supports_effect_model_like_object(self, game_state: GameState):
        effect_obj = SimpleNamespace(actions=[{"type": "add_points", "amount": 100}])
        new_state = run_effect(game_state, effect_obj)
        assert new_state.scores == (600, 300, 100)

    def test_none_effect_returns_state_unmodified(self, game_state: GameState):
        new_state = run_effect(game_state, None)
        assert new_state is game_state
