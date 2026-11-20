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
    sector_index: int = -1
    sector_value: int = 0
    cell_index: int = -1
    box_index: int = -1
    letters: tuple[str, ...] = ()
    duration: int = 60
    limit: int = 3


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


def start_spin() -> Action:
    """Start spinning the wheel."""
    return Action(type="START_SPIN")


def spin_result(sector_index: int, sector_value: int = 0) -> Action:
    """Apply the landed sector result."""
    return Action(type="SPIN_RESULT", sector_index=sector_index, sector_value=sector_value)


def reveal_cell(cell_index: int) -> Action:
    """Reveal a specific cell by index on the board (Sector '+')."""
    return Action(type="REVEAL_CELL", cell_index=cell_index)


def choose_box(box_index: int) -> Action:
    """Choose box 0 or 1 in two-boxes minigame."""
    return Action(type="CHOOSE_BOX", box_index=box_index)


def start_supergame(limit: int = 3, duration: int = 60) -> Action:
    """Start supergame round."""
    return Action(type="START_SUPERGAME", limit=limit, duration=duration)


def supergame_letters(letters: list[str] | tuple[str, ...]) -> Action:
    """Provide free letters in supergame."""
    return Action(type="SUPERGAME_LETTERS", letters=tuple(letters))


def supergame_time_up() -> Action:
    """Trigger gong when supergame countdown finishes."""
    return Action(type="SUPERGAME_TIME_UP")


def supergame_guess(correct: bool) -> Action:
    """Resolve supergame word guess."""
    return Action(type="SUPERGAME_GUESS", correct=correct)


def action_from_dict(data: dict) -> Action:
    """Parse an Action from a dictionary payload."""
    action_type = str(data.get("type", "")).upper()
    raw_letters = data.get("letters") or ()
    if isinstance(raw_letters, (list, tuple)):
        parsed_letters = tuple(str(x) for x in raw_letters)
    elif isinstance(raw_letters, str):
        parsed_letters = tuple(raw_letters.split())
    else:
        parsed_letters = ()

    return Action(
        type=action_type,
        letter=str(data.get("letter", "")),
        correct=bool(data.get("correct", False)),
        player=int(data.get("player", -1)),
        delta=int(data.get("delta", 0)),
        sector_index=int(data.get("sector_index", -1)),
        sector_value=int(data.get("sector_value", 0)),
        cell_index=int(data.get("cell_index", -1)),
        box_index=int(data.get("box_index", -1)),
        letters=parsed_letters,
        duration=int(data.get("duration", 60)),
        limit=int(data.get("limit", 3)),
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
        new_streak = state.letter_streak + 1
        is_won = is_fully_revealed(new_mask)

        # Check for 3 correct letters in a row (when round is still ongoing)
        if is_won:
            new_phase = "round_won"
            special_event = state.special_event
            pending_modal = state.pending_modal
            pending_sound = "letter_open"
            streak_to_store = new_streak
        elif new_streak >= 3:
            new_phase = "special_event"
            special_event = "two_boxes"
            pending_modal = "two_boxes"
            pending_sound = "box_game"
            streak_to_store = 0  # streak consumed
        else:
            new_phase = "await_letter"
            special_event = state.special_event
            pending_modal = state.pending_modal
            pending_sound = "letter_open"
            streak_to_store = new_streak

        return replace(
            state,
            phase=new_phase,
            mask=new_mask,
            scores=new_scores,
            guessed_letters=new_guessed,
            letter_streak=streak_to_store,
            special_event=special_event,
            pending_modal=pending_modal,
            pending_sound=pending_sound,
            version=state.version + 1,
        )

    # Miss — pass turn and reset streak.
    return replace(
        state,
        current_player=_next_player(state),
        guessed_letters=new_guessed,
        letter_streak=0,
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

    # Incorrect — pass turn and reset streak.
    return replace(
        state,
        current_player=_next_player(state),
        letter_streak=0,
        version=state.version + 1,
    )


def _skip_turn(state: GameState, action: Action) -> GameState:
    _require_phase(state, "await_letter", "skip turn")
    return replace(
        state,
        current_player=_next_player(state),
        letter_streak=0,
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


def _start_spin(state: GameState, action: Action) -> GameState:
    if state.phase not in ("idle", "await_letter", "turn_end"):
        raise InvalidAction(f"Cannot start spin in phase {state.phase!r}")
    return replace(
        state,
        phase="spinning",
        version=state.version + 1,
    )


def _spin_result(state: GameState, action: Action) -> GameState:
    if state.phase not in ("spinning", "await_letter", "idle"):
        raise InvalidAction(f"Cannot apply spin result in phase {state.phase!r}")

    new_sector_value = (
        action.sector_value if action.sector_value > 0 else state.sector_value
    )
    return replace(
        state,
        phase="await_letter",
        sector_index=action.sector_index,
        sector_value=new_sector_value,
        version=state.version + 1,
    )


def _reveal_cell(state: GameState, action: Action) -> GameState:
    """Reveal a specific closed cell on the board (Sector '+').

    Guarantees:
      - Can only be applied when special_event is 'reveal_any_letter' (or pending_modal 'reveal_cell').
      - Cell index must be valid and currently closed.
      - Can only be applied once (clears special_event).
    """
    if state.special_event != "reveal_any_letter" and state.pending_modal != "reveal_cell":
        raise InvalidAction("Cannot reveal cell: not in sector '+' special event")

    if action.cell_index < 0 or action.cell_index >= len(state.word):
        raise InvalidAction(
            f"Cell index {action.cell_index} is out of bounds (word length: {len(state.word)})"
        )

    if state.mask[action.cell_index]:
        raise InvalidAction(f"Cell #{action.cell_index} is already revealed")

    target_char = state.word[action.cell_index]
    norm_letter = normalize(target_char)
    new_mask = reveal_letter(state.word, state.mask, norm_letter)
    new_guessed = state.guessed_letters | {norm_letter}
    new_phase = "round_won" if is_fully_revealed(new_mask) else "await_letter"

    return replace(
        state,
        phase=new_phase,
        mask=new_mask,
        guessed_letters=new_guessed,
        special_event="",
        pending_modal="",
        pending_sound="letter_open",
        version=state.version + 1,
    )


def _choose_box(state: GameState, action: Action) -> GameState:
    """Choose box 0 or 1 in the two-boxes minigame.

    Guarantees:
      - Can only be applied when special_event is 'two_boxes'.
      - Box index must be 0 or 1.
      - Applied exactly once: clears special_event and transitions to await_letter.
    """
    if state.special_event != "two_boxes" and state.pending_modal != "two_boxes":
        raise InvalidAction("Cannot choose box: two-boxes game is not active")

    if action.box_index not in (0, 1):
        raise InvalidAction(f"Invalid box index {action.box_index}. Must be 0 or 1.")

    is_winner = (action.box_index == state.box_prize_index)
    points = state.box_points if state.box_points > 0 else 500

    if is_winner:
        new_scores = _add_score(state.scores, state.current_player, points)
        modal = f"box_win:{points}"
        sound = "win"
    else:
        new_scores = state.scores
        modal = "box_empty"
        sound = "miss"

    return replace(
        state,
        phase="await_letter",
        scores=new_scores,
        special_event="",
        pending_modal=modal,
        pending_sound=sound,
        version=state.version + 1,
    )


def _start_supergame(state: GameState, action: Action) -> GameState:
    from engine import supergame
    return supergame.start_supergame(
        state,
        free_letters_limit=action.limit,
        timer_duration=action.duration,
    )


def _supergame_letters(state: GameState, action: Action) -> GameState:
    from engine import supergame
    letters = action.letters if action.letters else ((action.letter,) if action.letter else ())
    return supergame.choose_free_letters(state, letters)


def _supergame_time_up(state: GameState, _action: Action) -> GameState:
    from engine import supergame
    return supergame.time_up(state)


def _supergame_guess(state: GameState, action: Action) -> GameState:
    from engine import supergame
    return supergame.resolve_supergame(state, correct=action.correct)


# ---- Register handlers ---------------------------------------------

_HANDLERS.update(
    {
        "GUESS_LETTER": _guess_letter,
        "GUESS_WORD": _guess_word,
        "SKIP_TURN": _skip_turn,
        "MANUAL_SCORE": _manual_score,
        "START_SPIN": _start_spin,
        "SPIN_RESULT": _spin_result,
        "REVEAL_CELL": _reveal_cell,
        "CHOOSE_BOX": _choose_box,
        "START_SUPERGAME": _start_supergame,
        "SUPERGAME_LETTERS": _supergame_letters,
        "SUPERGAME_TIME_UP": _supergame_time_up,
        "SUPERGAME_GUESS": _supergame_guess,
    }
)
