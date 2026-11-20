"""Actions and the pure ``apply()`` function.

``apply(state, action) -> GameState`` is the single entry-point.
It is **pure**: no database, no clock, no randomness.  The server
chooses the spin result beforehand and sends ``SPIN_RESULT``; the
animation merely visualises it.

Task 3 implements: GUESS_LETTER, GUESS_WORD, SKIP_TURN, MANUAL_SCORE.
Later tasks add: START_SPIN, SPIN_RESULT, REVEAL_CELL, CHOOSE_BOX,
UNDO, NEXT_ROUND.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine.state import GameState
from engine.words import (
    count_occurrences,
    is_fully_revealed,
    normalize,
    reveal_letter,
)


# ------------------------------------------------------------------ #
#  Exceptions
# ------------------------------------------------------------------ #


class InvalidAction(Exception):
    """Raised when an action cannot be applied to the current state."""


# ------------------------------------------------------------------ #
#  Action data
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class Action:
    """Lightweight action object.  Use the factory helpers below."""

    type: str
    letter: str = ""
    correct: bool = False
    player: int = -1
    delta: int = 0


# ---- Factory helpers ------------------------------------------------


def guess_letter(letter: str) -> Action:
    """Player guesses a single letter."""
    return Action(type="GUESS_LETTER", letter=letter)


def guess_word(correct: bool) -> Action:
    """Host confirms / denies a word guess."""
    return Action(type="GUESS_WORD", correct=correct)


def skip_turn() -> Action:
    """Skip the current player's turn."""
    return Action(type="SKIP_TURN")


def manual_score(player: int, delta: int) -> Action:
    """Host manually adjusts a player's score."""
    return Action(type="MANUAL_SCORE", player=player, delta=delta)


def action_from_dict(data: dict) -> Action:
    """Parse an Action from a dictionary payload."""
    action_type = str(data.get("type", "")).upper()
    return Action(
        type=action_type,
        letter=str(data.get("letter", "")),
        correct=bool(data.get("correct", False)),
        player=int(data.get("player", -1)),
        delta=int(data.get("delta", 0)),
    )


# ------------------------------------------------------------------ #
#  apply()
# ------------------------------------------------------------------ #

_HANDLERS: dict[str, _Handler] = {}  # filled below

# Type alias for readability
type _Handler = type[object]  # actually Callable, but we register below


def apply(state: GameState, action: Action) -> GameState:
    """Apply *action* to *state*, returning a **new** GameState.

    Raises ``InvalidAction`` for unknown or misplaced actions.
    """
    handler = _HANDLERS.get(action.type)
    if handler is None:
        raise InvalidAction(f"Unknown action: {action.type!r}")
    return handler(state, action)


# ------------------------------------------------------------------ #
#  Internal helpers
# ------------------------------------------------------------------ #


def _next_player(state: GameState) -> int:
    return (state.current_player + 1) % len(state.players)


def _add_score(
    scores: tuple[int, ...], player: int, delta: int
) -> tuple[int, ...]:
    return tuple(
        s + delta if i == player else s for i, s in enumerate(scores)
    )


def _require_phase(state: GameState, phase: str, action_name: str) -> None:
    if state.phase != phase:
        raise InvalidAction(
            f"Cannot {action_name} in phase {state.phase!r}"
        )


# ------------------------------------------------------------------ #
#  Handlers (registered into _HANDLERS)
# ------------------------------------------------------------------ #


def _guess_letter(state: GameState, action: Action) -> GameState:
    _require_phase(state, "await_letter", "guess letter")

    letter = normalize(action.letter)

    # Repeated letter — ignore, return the exact same object.
    if letter in state.guessed_letters:
        return state

    new_guessed = state.guessed_letters | {letter}
    hits = count_occurrences(state.word, letter)

    if hits > 0:
        new_mask = reveal_letter(state.word, state.mask, letter)

        if state.scoring == "per_occurrence":
            points = state.sector_value * hits
        else:  # per_letter
            points = state.sector_value

        new_scores = _add_score(state.scores, state.current_player, points)
        new_phase = "round_won" if is_fully_revealed(new_mask) else "await_letter"

        return replace(
            state,
            phase=new_phase,
            mask=new_mask,
            scores=new_scores,
            guessed_letters=new_guessed,
            version=state.version + 1,
        )

    # Miss — pass turn.
    return replace(
        state,
        current_player=_next_player(state),
        guessed_letters=new_guessed,
        version=state.version + 1,
    )


def _guess_word(state: GameState, action: Action) -> GameState:
    _require_phase(state, "await_letter", "guess word")

    if action.correct:
        full_mask = tuple(True for _ in state.mask)
        new_scores = _add_score(
            state.scores, state.current_player, state.word_bonus
        )
        return replace(
            state,
            phase="round_won",
            mask=full_mask,
            scores=new_scores,
            version=state.version + 1,
        )

    # Incorrect — pass turn.
    return replace(
        state,
        current_player=_next_player(state),
        version=state.version + 1,
    )


def _skip_turn(state: GameState, action: Action) -> GameState:
    _require_phase(state, "await_letter", "skip turn")
    return replace(
        state,
        current_player=_next_player(state),
        version=state.version + 1,
    )


def _manual_score(state: GameState, action: Action) -> GameState:
    if action.player < 0 or action.player >= len(state.players):
        raise InvalidAction(
            f"Invalid player index: {action.player} "
            f"(have {len(state.players)} players)"
        )
    return replace(
        state,
        scores=_add_score(state.scores, action.player, action.delta),
        version=state.version + 1,
    )


# ---- Register handlers ---------------------------------------------

_HANDLERS.update(
    {
        "GUESS_LETTER": _guess_letter,
        "GUESS_WORD": _guess_word,
        "SKIP_TURN": _skip_turn,
        "MANUAL_SCORE": _manual_score,
    }
)
