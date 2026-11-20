"""Supergame engine (Task 14).

Pure Python: handles supergame mechanics:
  - Free opening of 3-4 letters without awarding score points;
  - Server-calculated countdown timer (30 or 60 seconds from event rules);
  - Time expiration with gong sound;
  - Supergame outcome (win / loss).
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Sequence

from engine.actions import InvalidAction
from engine.state import GameState
from engine.words import normalize, reveal_letter


class SupergameError(InvalidAction):
    """Raised when an invalid supergame action occurs."""


def start_supergame(
    state: GameState,
    *,
    free_letters_limit: int = 3,
    timer_duration: int = 60,
) -> GameState:
    """Initialize supergame round for the finalist.

    Sets phase to 'supergame_selection' where player names 3-4 letters.
    """
    if free_letters_limit not in (3, 4):
        free_letters_limit = 3
    if timer_duration not in (30, 60):
        timer_duration = 60

    return replace(
        state,
        phase="supergame_selection",
        is_supergame=True,
        free_letters_limit=free_letters_limit,
        timer_duration=timer_duration,
        chosen_free_letters=(),
        timer_end_timestamp=None,
        pending_modal="supergame_selection",
        pending_sound="supergame_start",
        version=state.version + 1,
    )


def choose_free_letters(
    state: GameState,
    letters: Sequence[str],
    *,
    start_time: float | None = None,
) -> GameState:
    """Reveal 3-4 letters chosen by the player without awarding points and start timer.

    Server timestamp guarantees timer accuracy regardless of client browser tab state.
    """
    if state.phase != "supergame_selection":
        raise SupergameError(
            f"Cannot choose free letters in phase {state.phase!r}. Expected 'supergame_selection'."
        )

    norm_letters = [normalize(l) for l in letters if l and l.strip()]
    # Remove duplicates while preserving order
    unique_letters = tuple(dict.fromkeys(norm_letters))

    if len(unique_letters) > state.free_letters_limit:
        raise SupergameError(
            f"Allowed at most {state.free_letters_limit} free letters, got {len(unique_letters)}: {unique_letters}"
        )

    # Reveal occurrences in word WITHOUT awarding points (scores untouched)
    new_mask = state.mask
    new_guessed = set(state.guessed_letters)
    for l in unique_letters:
        new_mask = reveal_letter(state.word, new_mask, l)
        new_guessed.add(l)

    now = start_time if start_time is not None else time.time()
    timer_end = now + state.timer_duration

    return replace(
        state,
        phase="supergame_thinking",
        mask=new_mask,
        guessed_letters=frozenset(new_guessed),
        chosen_free_letters=unique_letters,
        timer_end_timestamp=timer_end,
        pending_modal="supergame_timer",
        pending_sound="timer_start",
        version=state.version + 1,
    )


def is_timer_expired(state: GameState, current_time: float | None = None) -> bool:
    """Check if server timer has expired."""
    if state.timer_end_timestamp is None:
        return False
    now = current_time if current_time is not None else time.time()
    return now >= state.timer_end_timestamp


def time_up(state: GameState) -> GameState:
    """Mark time expired and trigger gong."""
    if state.phase != "supergame_thinking":
        raise SupergameError(f"Cannot expire timer in phase {state.phase!r}")

    return replace(
        state,
        phase="supergame_lost",
        pending_modal="supergame_time_up",
        pending_sound="gong",
        version=state.version + 1,
    )


def resolve_supergame(state: GameState, correct: bool) -> GameState:
    """Finalize supergame: victory or defeat."""
    if state.phase not in ("supergame_selection", "supergame_thinking", "supergame_lost"):
        raise SupergameError(f"Cannot resolve supergame in phase {state.phase!r}")

    if correct:
        full_mask = tuple(True for _ in state.mask)
        return replace(
            state,
            phase="supergame_won",
            mask=full_mask,
            pending_modal="supergame_win",
            pending_sound="win",
            version=state.version + 1,
        )

    return replace(
        state,
        phase="supergame_lost",
        pending_modal="supergame_lost",
        pending_sound="gong",
        version=state.version + 1,
    )
