"""Tests for Special Mechanics (Task 13): Sector «+», Two Boxes, and Modal events."""

import pytest

from engine.actions import (
    InvalidAction,
    apply,
    choose_box,
    guess_letter,
    reveal_cell,
)
from engine.effects import run_effect
from engine.state import GameState, new_game


@pytest.fixture()
def game_state() -> GameState:
    """Game with word 'ДОЛОМИТ' and 3 players."""
    return new_game(
        word="ДОЛОМИТ",
        players=["Анна", "Борис", "Вера"],
        sector_value=100,
    )


class TestSectorPlusRevealCell:
    def test_sector_plus_activates_special_event(self, game_state: GameState):
        """Сектор '+' переводит игру в режим выбора клетки."""
        state = run_effect(game_state, "reveal_any_letter")
        assert state.phase == "special_event"
        assert state.special_event == "reveal_any_letter"
        assert state.pending_modal == "reveal_cell"

    def test_reveal_cell_opens_letter_and_clears_special_event(self, game_state: GameState):
        """«+» разрешает открыть любую закрытую клетку один раз."""
        state = run_effect(game_state, "reveal_any_letter")

        # Cell index 0 corresponds to 'Д' in 'ДОЛОМИТ'
        assert not state.mask[0]
        new_state = apply(state, reveal_cell(0))

        # 'Д' should now be revealed
        assert new_state.mask[0] is True
        assert "д" in new_state.guessed_letters
        # Special event cleared, back to await_letter
        assert new_state.phase == "await_letter"
        assert new_state.special_event == ""
        assert new_state.pending_modal == ""

    def test_reveal_cell_applies_strictly_once(self, game_state: GameState):
        """Повторный вызов REVEAL_CELL запрещён: применяется ровно один раз."""
        state = run_effect(game_state, "reveal_any_letter")
        state_after_first = apply(state, reveal_cell(0))

        # Calling REVEAL_CELL again must raise InvalidAction
        with pytest.raises(InvalidAction) as exc:
            apply(state_after_first, reveal_cell(1))
        assert "not in sector '+' special event" in str(exc.value)

    def test_reveal_cell_on_already_revealed_cell_fails(self, game_state: GameState):
        """Нельзя открыть уже открытую букву."""
        # First guess 'Д' normally
        state1 = apply(game_state, guess_letter("Д"))
        assert state1.mask[0] is True

        # Now trigger '+'
        state_plus = run_effect(state1, "reveal_any_letter")

        # Attempt to reveal cell 0 again
        with pytest.raises(InvalidAction) as exc:
            apply(state_plus, reveal_cell(0))
        assert "already revealed" in str(exc.value)

    def test_reveal_cell_out_of_bounds_fails(self, game_state: GameState):
        state = run_effect(game_state, "reveal_any_letter")
        with pytest.raises(InvalidAction):
            apply(state, reveal_cell(99))


class TestThreeLettersStreakAndTwoBoxes:
    def test_streak_of_three_correct_letters_triggers_box_game(self, game_state: GameState):
        """Серия из трёх угаданных букв подряд запускает start_box_game."""
        # Word is 'ДОЛОМИТ'
        assert game_state.letter_streak == 0

        # Guess 1: 'Д'
        s1 = apply(game_state, guess_letter("Д"))
        assert s1.letter_streak == 1
        assert s1.phase == "await_letter"

        # Guess 2: 'О'
        s2 = apply(s1, guess_letter("О"))
        assert s2.letter_streak == 2
        assert s2.phase == "await_letter"

        # Guess 3: 'Л' -> 3rd in a row!
        s3 = apply(s2, guess_letter("Л"))
        # Should trigger two_boxes
        assert s3.phase == "special_event"
        assert s3.special_event == "two_boxes"
        assert s3.pending_modal == "two_boxes"
        # Streak is consumed / reset
        assert s3.letter_streak == 0

    def test_miss_resets_letter_streak(self, game_state: GameState):
        """Неверная буква сбрасывает счётчик серии."""
        s1 = apply(game_state, guess_letter("Д"))
        assert s1.letter_streak == 1

        # Miss with 'Я'
        s2 = apply(s1, guess_letter("Я"))
        assert s2.letter_streak == 0
        assert s2.current_player == 1  # turn passed


class TestTwoBoxesGame:
    def test_choose_winning_box_awards_points(self, game_state: GameState):
        """Выбор выигрышной шкатулки начисляет очки и применяется один раз."""
        # Setup box game: winning box is index 0, points = 500
        box_state = run_effect(game_state, "start_box_game")
        assert box_state.special_event == "two_boxes"
        assert box_state.box_prize_index == 0

        initial_score = box_state.scores[box_state.current_player]
        winner_state = apply(box_state, choose_box(0))

        assert winner_state.scores[box_state.current_player] == initial_score + 500
        assert winner_state.special_event == ""
        assert winner_state.phase == "await_letter"
        assert "box_win:500" in winner_state.pending_modal

    def test_choose_empty_box_gives_no_points(self, game_state: GameState):
        """Выбор пустой шкатулки не начисляет очки."""
        box_state = run_effect(game_state, "start_box_game")
        initial_score = box_state.scores[box_state.current_player]

        # Box 1 is empty
        empty_state = apply(box_state, choose_box(1))
        assert empty_state.scores[box_state.current_player] == initial_score
        assert empty_state.special_event == ""
        assert empty_state.phase == "await_letter"
        assert empty_state.pending_modal == "box_empty"

    def test_box_result_applies_strictly_once(self, game_state: GameState):
        """Результат шкатулки применяется ровно один раз."""
        box_state = run_effect(game_state, "start_box_game")
        state_after = apply(box_state, choose_box(0))

        # Second choice must fail
        with pytest.raises(InvalidAction) as exc:
            apply(state_after, choose_box(1))
        assert "two-boxes game is not active" in str(exc.value)

    def test_invalid_box_index_fails(self, game_state: GameState):
        box_state = run_effect(game_state, "start_box_game")
        with pytest.raises(InvalidAction):
            apply(box_state, choose_box(2))
