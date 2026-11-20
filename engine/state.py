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
    multiplier: int = 1  # score multiplier from special sectors (e.g. x2)
    special_event: str = ""  # active special event (e.g. reveal_any_letter, two_boxes)
    pending_modal: str = ""  # modal window to display on frontend
    pending_sound: str = ""  # sound trigger to play
    letter_streak: int = 0  # consecutive correct letters guessed by current player
    box_prize_index: int = 0  # index of winning box in two-boxes minigame (0 or 1)
    box_points: int = 500  # points awarded for choosing the winning box
    is_supergame: bool = False  # True during supergame round
    timer_end_timestamp: float | None = None  # Absolute server epoch timestamp when timer expires
    timer_duration: int = 60  # Timer duration in seconds (30 or 60)
    free_letters_limit: int = 3  # Number of free letters allowed in supergame (3 or 4)
    chosen_free_letters: tuple[str, ...] = ()  # Letters chosen by player during supergame
    tv_mode: bool = False  # Strict TV Mode: each turn requires spinning wheel before letter


def new_game(
    word: str,
    players: tuple[str, ...] | list[str],
    *,
    phase: str = "",
    scoring: str = "per_occurrence",
    word_bonus: int = 0,
    sector_value: int = 0,
    question: str = "",
    hint: str = "",
    sector_index: int = -1,
    multiplier: int = 1,
    special_event: str = "",
    pending_modal: str = "",
    pending_sound: str = "",
    letter_streak: int = 0,
    box_prize_index: int = 0,
    box_points: int = 500,
    is_supergame: bool = False,
    timer_end_timestamp: float | None = None,
    timer_duration: int = 60,
    free_letters_limit: int = 3,
    chosen_free_letters: tuple[str, ...] = (),
    tv_mode: bool = False,
) -> GameState:
    """Create a fresh game state for a round.

    In standard mode, the game starts in ``await_letter``.
    In TV mode (tv_mode=True and not is_supergame), the game starts in ``idle``
    (awaiting spin).
    Non-alphabetic characters (hyphens, spaces) are pre-revealed.
    """
    players_tuple = tuple(players)
    if phase:
        initial_phase = phase
    elif tv_mode and not is_supergame:
        initial_phase = "idle"
    else:
        initial_phase = "await_letter"

    init_sector_val = 0 if (tv_mode and not is_supergame and sector_value == 0) else sector_value

    return GameState(
        phase=initial_phase,
        word=word,
        mask=make_mask(word),
        players=players_tuple,
        current_player=0,
        scores=tuple(0 for _ in players_tuple),
        guessed_letters=frozenset(),
        sector_value=init_sector_val,
        scoring=scoring,
        word_bonus=word_bonus,
        version=0,
        question=question,
        hint=hint,
        sector_index=sector_index,
        multiplier=multiplier,
        special_event=special_event,
        pending_modal=pending_modal,
        pending_sound=pending_sound,
        letter_streak=letter_streak,
        box_prize_index=box_prize_index,
        box_points=box_points,
        is_supergame=is_supergame,
        timer_end_timestamp=timer_end_timestamp,
        timer_duration=timer_duration,
        free_letters_limit=free_letters_limit,
        chosen_free_letters=chosen_free_letters,
        tv_mode=tv_mode,
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
        "multiplier": state.multiplier,
        "special_event": state.special_event,
        "pending_modal": state.pending_modal,
        "pending_sound": state.pending_sound,
        "letter_streak": state.letter_streak,
        "box_prize_index": state.box_prize_index,
        "box_points": state.box_points,
        "is_supergame": state.is_supergame,
        "timer_end_timestamp": state.timer_end_timestamp,
        "timer_duration": state.timer_duration,
        "free_letters_limit": state.free_letters_limit,
        "chosen_free_letters": list(state.chosen_free_letters),
        "tv_mode": state.tv_mode,
    }


def dict_to_state(data: dict) -> GameState:
    """Deserialize GameState from a dictionary."""
    timer_end = data.get("timer_end_timestamp")
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
        multiplier=int(data.get("multiplier", 1)),
        special_event=str(data.get("special_event", "")),
        pending_modal=str(data.get("pending_modal", "")),
        pending_sound=str(data.get("pending_sound", "")),
        letter_streak=int(data.get("letter_streak", 0)),
        box_prize_index=int(data.get("box_prize_index", 0)),
        box_points=int(data.get("box_points", 500)),
        is_supergame=bool(data.get("is_supergame", False)),
        timer_end_timestamp=float(timer_end) if timer_end is not None else None,
        timer_duration=int(data.get("timer_duration", 60)),
        free_letters_limit=int(data.get("free_letters_limit", 3)),
        chosen_free_letters=tuple(data.get("chosen_free_letters", ())),
        tv_mode=bool(data.get("tv_mode", False)),
    )
