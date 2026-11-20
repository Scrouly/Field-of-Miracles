"""Effects engine (Task 8).

Pure Python: interprets Effect configurations and applies them to GameState.
Supported actions from section 5:
  - bankrupt: zeros the current player's score and passes the turn.
  - multiply: multiplies points (sector_value and multiplier factor).
  - skip_turn: passes the turn to the next player.
  - add_points: adds points to the current player.
  - reveal_any_letter: triggers special event (sector '+').
  - start_box_game: triggers the two boxes mini-game.
  - show_modal: triggers a modal dialog on the client.
  - play_sound: queues a sound trigger.
  - give_prize: grants a prize.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from engine.actions import InvalidAction
from engine.state import GameState


class UnknownEffectAction(InvalidAction, ValueError):
    """Raised when an effect action type is not recognized."""


# ------------------------------------------------------------------ #
#  Internal Handlers
# ------------------------------------------------------------------ #


def _effect_bankrupt(state: GameState, _data: dict[str, Any]) -> GameState:
    """Банкрот: обнуляет очки текущего игрока и передаёт ход."""
    num_players = len(state.players)
    next_player = (state.current_player + 1) % num_players if num_players > 0 else 0

    new_scores = tuple(
        0 if i == state.current_player else s
        for i, s in enumerate(state.scores)
    )

    return replace(
        state,
        scores=new_scores,
        current_player=next_player,
        multiplier=1,
        pending_sound="bankrupt",
        version=state.version + 1,
    )


def _effect_multiply(state: GameState, data: dict[str, Any]) -> GameState:
    """Multiply: умножает очки сектора на коэффициент (по умолчанию 2)."""
    factor = int(data.get("factor", 2))
    base_val = state.sector_value if state.sector_value > 0 else 100
    new_val = base_val * factor
    new_mult = state.multiplier * factor

    return replace(
        state,
        sector_value=new_val,
        multiplier=new_mult,
        version=state.version + 1,
    )


def _effect_skip_turn(state: GameState, _data: dict[str, Any]) -> GameState:
    """Skip turn: передаёт ход следующему игроку без потери очков."""
    num_players = len(state.players)
    next_player = (state.current_player + 1) % num_players if num_players > 0 else 0

    return replace(
        state,
        current_player=next_player,
        version=state.version + 1,
    )


def _effect_add_points(state: GameState, data: dict[str, Any]) -> GameState:
    """Add points: начисляет фиксированные очки текущему игроку."""
    amount = int(data.get("amount", 0))
    new_scores = tuple(
        s + amount if i == state.current_player else s
        for i, s in enumerate(state.scores)
    )
    return replace(
        state,
        scores=new_scores,
        version=state.version + 1,
    )


def _effect_reveal_any_letter(state: GameState, _data: dict[str, Any]) -> GameState:
    """Сектор «+»: переход в спец-фазу для выбора любой закрытой клетки."""
    return replace(
        state,
        phase="special_event",
        special_event="reveal_any_letter",
        version=state.version + 1,
    )


def _effect_start_box_game(state: GameState, _data: dict[str, Any]) -> GameState:
    """Две шкатулки: мини-игра на выбор одной из двух шкатулок."""
    return replace(
        state,
        phase="special_event",
        special_event="two_boxes",
        pending_modal="two_boxes",
        version=state.version + 1,
    )


def _effect_show_modal(state: GameState, data: dict[str, Any]) -> GameState:
    """Показ модального окна на экране."""
    modal_name = str(data.get("modal") or data.get("name") or data.get("message") or "info")
    return replace(
        state,
        phase="special_event",
        pending_modal=modal_name,
        version=state.version + 1,
    )


def _effect_play_sound(state: GameState, data: dict[str, Any]) -> GameState:
    """Воспроизведение звука по триггеру."""
    sound_trigger = str(data.get("sound") or data.get("trigger") or "")
    return replace(
        state,
        pending_sound=sound_trigger,
        version=state.version + 1,
    )


def _effect_give_prize(state: GameState, data: dict[str, Any]) -> GameState:
    """Выдача приза игроку."""
    prize_name = str(data.get("prize") or data.get("name") or "Приз")
    return replace(
        state,
        phase="special_event",
        pending_modal=f"prize:{prize_name}",
        version=state.version + 1,
    )


_EFFECT_DISPATCH: dict[str, Callable[[GameState, dict[str, Any]], GameState]] = {
    "bankrupt": _effect_bankrupt,
    "multiply": _effect_multiply,
    "skip_turn": _effect_skip_turn,
    "add_points": _effect_add_points,
    "reveal_any_letter": _effect_reveal_any_letter,
    "start_box_game": _effect_start_box_game,
    "show_modal": _effect_show_modal,
    "play_sound": _effect_play_sound,
    "give_prize": _effect_give_prize,
}


# ------------------------------------------------------------------ #
#  Public Interface
# ------------------------------------------------------------------ #


def run_effect(state: GameState, effect: Any) -> GameState:
    """Execute an effect or sequence of actions on the given GameState.

    Parameters:
      - state: immutable GameState
      - effect: Effect model instance, dict, list of action dicts/strings, or action string.

    Returns:
      New GameState reflecting the applied actions.

    Raises:
      UnknownEffectAction: if any action type in the effect is unrecognized.
    """
    if effect is None:
        return state

    # Extract list of actions
    if hasattr(effect, "actions") and isinstance(effect.actions, (list, tuple)):
        raw_actions = list(effect.actions)
    elif isinstance(effect, dict) and "actions" in effect and isinstance(effect["actions"], (list, tuple)):
        raw_actions = list(effect["actions"])
    elif isinstance(effect, (list, tuple)):
        raw_actions = list(effect)
    elif isinstance(effect, dict):
        raw_actions = [effect]
    elif isinstance(effect, str):
        raw_actions = [{"type": effect}]
    else:
        return state

    current_state = state

    for item in raw_actions:
        if isinstance(item, str):
            action_data = {"type": item}
        elif isinstance(item, dict):
            action_data = item
        else:
            continue

        raw_type = action_data.get("type", "")
        action_type = str(raw_type).strip().lower()

        handler = _EFFECT_DISPATCH.get(action_type)
        if handler is None:
            raise UnknownEffectAction(
                f"Неизвестный тип действия эффекта: '{raw_type}'. "
                f"Поддерживаемые типы: {', '.join(sorted(_EFFECT_DISPATCH.keys()))}"
            )

        current_state = handler(current_state, action_data)

    return current_state
