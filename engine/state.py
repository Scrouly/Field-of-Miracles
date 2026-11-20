"""Game state: a single immutable object representing the entire game.

Every action produces a new GameState via ``dataclasses.replace()``.
The ``version`` counter enables optimistic locking in the API layer.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.words import make_mask


@dataclass(frozen=True)
class GameState:
    """Immutable snapshot of the game round.

    Fields added by later tasks (effects, supergame, etc.) will get
    default values so existing code keeps working.
    """

    phase: str  # idle | await_letter | round_won | …
    word: str  # original word (for display)
    mask: tuple[bool, ...]  # True = revealed position
    players: tuple[str, ...]  # player names in seating order
    current_player: int  # index into ``players``
    scores: tuple[int, ...]  # parallel to ``players``
    guessed_letters: frozenset[str]  # normalized letters already tried
    sector_value: int  # points from current spin
    scoring: str  # per_letter | per_occurrence
    word_bonus: int  # bonus for guessing the whole word
    version: int  # incremented on every state change
    question: str = ""  # question text for display / host
    hint: str = ""  # hint for host
    sector_index: int = -1  # index of current/last landed sector on wheel


def new_game(
    word: str,
    players: tuple[str, ...] | list[str],
    *,
    scoring: str = "per_occurrence",
    word_bonus: int = 0,
    sector_value: int = 0,
    question: str = "",
    hint: str = "",
    sector_index: int = -1,
) -> GameState:
    """Create a fresh game state for a round.

    The game starts in ``await_letter`` with all alphabetic characters
    hidden.  Non-alphabetic characters (hyphens, spaces) are
    pre-revealed.
    """
    players_tuple = tuple(players)
    return GameState(
        phase="await_letter",
        word=word,
        mask=make_mask(word),
        players=players_tuple,
        current_player=0,
        scores=tuple(0 for _ in players_tuple),
        guessed_letters=frozenset(),
        sector_value=sector_value,
        scoring=scoring,
        word_bonus=word_bonus,
        version=0,
        question=question,
        hint=hint,
        sector_index=sector_index,
    )


def state_to_dict(state: GameState) -> dict:
    """Serialize GameState to a JSON-compatible dictionary."""
    return {
        "phase": state.phase,
        "word": state.word,
        "mask": list(state.mask),
        "players": list(state.players),
        "current_player": state.current_player,
        "scores": list(state.scores),
        "guessed_letters": sorted(state.guessed_letters),
        "sector_value": state.sector_value,
        "scoring": state.scoring,
        "word_bonus": state.word_bonus,
        "version": state.version,
        "question": state.question,
        "hint": state.hint,
        "sector_index": state.sector_index,
    }


def dict_to_state(data: dict) -> GameState:
    """Deserialize GameState from a dictionary."""
    return GameState(
        phase=data.get("phase", "idle"),
        word=data.get("word", ""),
        mask=tuple(bool(x) for x in data.get("mask", ())),
        players=tuple(data.get("players", ())),
        current_player=int(data.get("current_player", 0)),
        scores=tuple(int(x) for x in data.get("scores", ())),
        guessed_letters=frozenset(data.get("guessed_letters", ())),
        sector_value=int(data.get("sector_value", 0)),
        scoring=str(data.get("scoring", "per_occurrence")),
        word_bonus=int(data.get("word_bonus", 0)),
        version=int(data.get("version", 0)),
        question=str(data.get("question", "")),
        hint=str(data.get("hint", "")),
        sector_index=int(data.get("sector_index", -1)),
    )
