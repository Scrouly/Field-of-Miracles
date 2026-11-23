"""Game service layer.

Coordinates GameSession persistence, optimistic locking with versioning,
GameLog journaling, and pure engine transitions.
"""

from __future__ import annotations

from dataclasses import replace
import time
from typing import Any

from django.db import transaction

from apps.core.defaults import default_rules
from apps.core.models import Event, GameLog, GameSession, Round, Theme
from engine.actions import Action, InvalidAction, action_from_dict
from engine.actions import apply as engine_apply
from engine.effects import run_effect
from engine.state import (
    GameState,
    dict_to_state,
    new_game,
    state_to_dict,
)


class VersionConflict(Exception):
    """Raised when expected_version does not match the session's current version."""

    def __init__(
        self,
        message: str,
        current_version: int,
        current_state: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.current_version = current_version
        self.current_state = current_state


class SessionNotFound(Exception):
    """Raised when a requested GameSession does not exist."""


def get_or_create_session(
    session_id: int | None = None,
    event_id: int | None = None,
) -> GameSession:
    """Retrieve an active GameSession or create an initial one for the event."""
    if session_id is not None:
        try:
            return GameSession.objects.get(pk=session_id)
        except GameSession.DoesNotExist as exc:
            raise SessionNotFound(f"Игровая сессия #{session_id} не найдена") from exc

    # Find the target event
    if event_id is not None:
        event = Event.objects.get(pk=event_id)
    else:
        event = (
            Event.objects.filter(is_active=True).first()
            or Event.objects.first()
        )
        if event is None:
            theme, _ = Theme.objects.get_or_create(
                name="По умолчанию",
                defaults={"colors": {}, "fonts": {}},
            )
            event = Event.objects.create(
                name="Поле чудес — Основная игра",
                theme=theme,
                rules=default_rules(),
                is_active=True,
            )

    # Find an unfinished session for this event
    session = (
        GameSession.objects.filter(event=event, finished_at__isnull=True)
        .order_by("-started_at")
        .first()
    )

    if session is not None and session.state:
        return session

    init_state = get_initial_state_for_event(event)
    state_dict = state_to_dict(init_state)

    if session is not None:
        session.state = state_dict
        session.version = init_state.version
        session.save(update_fields=["state", "version"])
    else:
        session = GameSession.objects.create(
            event=event,
            state=state_dict,
            version=init_state.version,
        )

    return session


def get_initial_state_for_event(event: Event) -> GameState:
    """Construct a clean initial GameState based on an Event and its rounds/players."""
    first_round = (
        event.rounds.select_related("question").order_by("order").first()
    )
    if first_round and first_round.question:
        word = first_round.question.word
        question_text = first_round.question.text
        hint = first_round.question.hint
    else:
        word = "ДОЛОМИТ"
        question_text = "Минерал и предприятие"
        hint = "Горная порода"

    if first_round and first_round.params and first_round.params.get("players"):
        players = list(first_round.params["players"])
    else:
        all_players = list(
            event.players.order_by("order").values_list("name", flat=True)
        )
        if len(all_players) >= 3:
            players = all_players[:3]
        else:
            players = all_players or ["Игрок 1", "Игрок 2", "Игрок 3"]

    rules = event.rules or {}
    scoring = rules.get("scoring", "per_occurrence")
    word_bonus = rules.get("word_bonus", 0)
    tv_mode = bool(rules.get("tv_mode", False))
    is_super = (first_round.type == Round.Type.SUPERGAME) if first_round else False

    return new_game(
        word=word,
        players=players,
        scoring=scoring,
        word_bonus=word_bonus,
        sector_value=100 if not tv_mode else 0,
        question=question_text,
        hint=hint,
        tv_mode=tv_mode,
        is_supergame=is_super,
    )


def get_state_data(
    session_id: int | None = None,
    since: int | None = None,
) -> dict[str, Any]:
    """Return the state data dictionary, or a 'no_news' indicator if version <= since."""
    session = get_or_create_session(session_id=session_id)

    if since is not None and since >= session.version:
        return {
            "status": "no_news",
            "message": "без новостей",
            "changed": False,
            "version": session.version,
        }

    state_dict = dict(session.state)
    state_dict["version"] = session.version
    server_now = time.time()

    sectors_list = []
    try:
        round_obj = (
            session.event.rounds.filter(question__word=session.state.get("word"))
            .select_related("wheel")
            .first()
            or session.event.rounds.select_related("wheel")
            .order_by("order")
            .first()
        )
        if round_obj and round_obj.wheel:
            sectors_list = [
                {
                    "id": s.id,
                    "label": s.label,
                    "color": s.color,
                    "value": s.value,
                    "order": s.order,
                }
                for s in round_obj.wheel.sectors.order_by("order")
            ]
    except Exception:
        pass

    return {
        **state_dict,
        "sectors": sectors_list,
        "status": "ok",
        "changed": True,
        "version": session.version,
        "session_id": session.pk,
        "server_time": server_now,
        "state": state_dict,
    }


def _apply_action_with_effects(
    state: GameState,
    action: Action,
    session: GameSession,
) -> GameState:
    """Apply an action and evaluate any associated sector effects."""
    new_state = engine_apply(state, action)

    # Apply sector effect if SPIN_RESULT has an associated Effect in DB
    if action.type == "SPIN_RESULT" and action.sector_index >= 0:
        round_obj = (
            session.event.rounds.filter(question__word=state.word)
            .select_related("wheel")
            .first()
            or session.event.rounds.select_related("wheel")
            .order_by("order")
            .first()
        )
        if round_obj and round_obj.wheel:
            sectors = list(
                round_obj.wheel.sectors.select_related("effect").order_by("order")
            )
            if 0 <= action.sector_index < len(sectors):
                sector_obj = sectors[action.sector_index]
                if sector_obj.effect:
                    new_state = run_effect(new_state, sector_obj.effect)

    return new_state


def apply_action(
    action_data: dict[str, Any],
    expected_version: int,
    session_id: int | None = None,
) -> dict[str, Any]:
    """Atomically apply an action to the session, logging the action and handling versioning.

    Raises VersionConflict if expected_version != session.version.
    Raises InvalidAction if the engine rejects the action.
    """
    with transaction.atomic():
        if session_id is not None:
            try:
                session = GameSession.objects.select_for_update().get(pk=session_id)
            except GameSession.DoesNotExist as exc:
                raise SessionNotFound(f"Игровая сессия #{session_id} не найдена") from exc
        else:
            default_session = get_or_create_session()
            session = GameSession.objects.select_for_update().get(pk=default_session.pk)

        if expected_version != session.version:
            raise VersionConflict(
                f"Версия состояния устарела: ожидалась {expected_version}, на сервере {session.version}",
                current_version=session.version,
                current_state=session.state,
            )

        if action_data.get("type", "").upper() == "UNDO":
            return undo_last_action(session)

        if action_data.get("type", "").upper() == "LOAD_ROUND":
            round_id = action_data.get("round_id")
            if not round_id:
                raise InvalidAction("Параметр 'round_id' обязателен для LOAD_ROUND")
            new_state_dict = load_round_for_session(session, int(round_id))
            return {
                **new_state_dict,
                "status": "ok",
                "changed": True,
                "version": session.version,
                "session_id": session.pk,
                "state": new_state_dict,
            }

        if action_data.get("type", "").upper() == "RESET_ROUND":
            current_state = dict_to_state(session.state)
            init_state = new_game(
                word=current_state.word,
                players=list(current_state.players),
                scoring=current_state.scoring,
                word_bonus=current_state.word_bonus,
                sector_value=100 if not current_state.tv_mode else 0,
                question=current_state.question,
                hint=current_state.hint,
                is_supergame=current_state.is_supergame,
                tv_mode=current_state.tv_mode,
            )
            new_state_dict = state_to_dict(init_state)
            session.state = new_state_dict
            session.version = session.version + 1
            session.save(update_fields=["state", "version"])
            GameLog.objects.create(
                session=session,
                number=session.logs.count() + 1,
                action="RESET_ROUND",
                data={"word": current_state.word},
            )
            return {
                **new_state_dict,
                "status": "ok",
                "changed": True,
                "version": session.version,
                "session_id": session.pk,
                "state": new_state_dict,
            }

        action: Action = action_from_dict(action_data)
        current_state: GameState = dict_to_state(session.state)

        new_state: GameState = _apply_action_with_effects(current_state, action, session)

        # Record action in GameLog
        last_log = session.logs.order_by("-number").first()
        next_number = (last_log.number + 1) if last_log else 1

        GameLog.objects.create(
            session=session,
            number=next_number,
            action=action.type,
            data=action_data,
        )

        new_state_dict = state_to_dict(new_state)
        session.state = new_state_dict
        session.version = new_state.version
        session.save(update_fields=["state", "version"])

        return {
            **new_state_dict,
            "status": "ok",
            "changed": True,
            "version": session.version,
            "session_id": session.pk,
            "state": new_state_dict,
        }


def undo_last_action(session: GameSession) -> dict[str, Any]:
    """Roll back the last action in the session by deleting its log and replaying."""
    logs = list(session.logs.order_by("number"))
    if not logs:
        state_dict = dict(session.state)
        return {
            **state_dict,
            "status": "ok",
            "changed": False,
            "version": session.version,
            "session_id": session.pk,
            "state": state_dict,
        }

    # Delete the most recent log entry
    last_log = logs.pop()
    last_log.delete()

    # Replay all remaining logs from the event's initial state
    current_state = get_initial_state_for_event(session.event)
    for log in logs:
        if log.action == "LOAD_ROUND":
            r_id = log.data.get("round_id")
            if r_id:
                current_state = _get_round_initial_state(session.event, int(r_id))
        elif log.action == "RESET_ROUND":
            current_state = new_game(
                word=current_state.word,
                players=list(current_state.players),
                scoring=current_state.scoring,
                word_bonus=current_state.word_bonus,
                sector_value=100 if not current_state.tv_mode else 0,
                question=current_state.question,
                hint=current_state.hint,
                is_supergame=current_state.is_supergame,
                tv_mode=current_state.tv_mode,
            )
        else:
            action = action_from_dict(log.data)
            current_state = _apply_action_with_effects(current_state, action, session)

    # Next version for client invalidation
    new_version = session.version + 1
    new_state = replace(current_state, version=new_version)
    new_state_dict = state_to_dict(new_state)

    session.state = new_state_dict
    session.version = new_version
    session.save(update_fields=["state", "version"])

    return {
        **new_state_dict,
        "status": "ok",
        "changed": True,
        "version": session.version,
        "session_id": session.pk,
        "state": new_state_dict,
    }


def get_session_logs(
    session_id: int | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return recent action logs for the host panel."""
    session = get_or_create_session(session_id=session_id)
    logs = session.logs.order_by("-number")[:limit]
    return [
        {
            "number": log.number,
            "action": log.action,
            "data": log.data,
            "created_at": log.created_at.strftime("%H:%M:%S"),
        }
        for log in logs
    ]


def _get_round_initial_state(event: Event, round_id: int) -> GameState:
    """Construct initial state for a specific round."""
    try:
        round_obj = Round.objects.select_related("question", "wheel").get(pk=round_id, event=event)
    except Round.DoesNotExist as exc:
        raise InvalidAction(f"Раунд #{round_id} не найден в данном мероприятии") from exc

    question = round_obj.question
    word = question.word if question else "ДОЛОМИТ"
    question_text = question.text if question else "Вопрос раунда"
    hint = question.hint if question else ""

    players = round_obj.params.get("players") if round_obj.params else None
    if not players:
        all_players = list(event.players.order_by("order").values_list("name", flat=True))
        offset = (round_obj.order - 1) * 3
        if len(all_players) >= offset + 3:
            players = all_players[offset : offset + 3]
        elif len(all_players) >= 3:
            players = all_players[:3]
        else:
            players = all_players or ["Игрок 1", "Игрок 2", "Игрок 3"]

    rules = event.rules or {}
    scoring = rules.get("scoring", "per_occurrence")
    word_bonus = rules.get("word_bonus", 500)
    is_super = (round_obj.type == Round.Type.SUPERGAME)
    tv_mode = bool(rules.get("tv_mode", False))

    init_state = new_game(
        word=word,
        players=players,
        scoring=scoring,
        word_bonus=word_bonus,
        sector_value=100 if not tv_mode else 0,
        question=question_text,
        hint=hint,
        tv_mode=tv_mode,
        is_supergame=is_super,
    )
    return init_state


def load_round_for_session(session: GameSession, round_id: int) -> dict[str, Any]:
    """Switch the session to a specific round from the event."""
    init_state = _get_round_initial_state(session.event, round_id)
    round_obj = Round.objects.get(pk=round_id, event=session.event)

    state_dict = state_to_dict(init_state)
    session.state = state_dict
    session.version = session.version + 1
    session.save(update_fields=["state", "version"])

    GameLog.objects.create(
        session=session,
        number=session.logs.count() + 1,
        action="LOAD_ROUND",
        data={"round_id": round_id, "round_order": round_obj.order, "word": init_state.word},
    )
    return state_dict


def reset_test_game(event_id: int | None = None) -> GameSession:
    """Completely reset the test game session to Tour 1 with clean state."""
    if event_id:
        event = Event.objects.get(pk=event_id)
    else:
        event = Event.objects.filter(is_active=True).first() or Event.objects.first()
    if not event:
        from apps.core.management.commands.setup_demo import populate_dolomit_demo
        event = populate_dolomit_demo()

    first_round = event.rounds.select_related("question").order_by("order").first()
    question = first_round.question if first_round else None
    word = question.word if question else "ДОЛОМИТ"
    question_text = question.text if question else "Главный минерал предприятия"
    hint = question.hint if question else "Название предприятия"

    players = first_round.params.get("players") if first_round and first_round.params else None
    if not players:
        players = ["Иван Кузнецов", "Елена Смирнова", "Сергей Морозов"]

    rules = event.rules or {}
    scoring = rules.get("scoring", "per_occurrence")
    word_bonus = rules.get("word_bonus", 500)
    tv_mode = bool(rules.get("tv_mode", True))

    init_state = new_game(
        word=word,
        players=players,
        scoring=scoring,
        word_bonus=word_bonus,
        sector_value=100 if not tv_mode else 0,
        question=question_text,
        hint=hint,
        tv_mode=tv_mode,
    )
    state_dict = state_to_dict(init_state)

    session = GameSession.objects.filter(event=event).order_by("-started_at").first()
    if not session:
        session = GameSession.objects.create(event=event, state=state_dict, version=0)
    else:
        session.state = state_dict
        session.version = 0
        session.logs.all().delete()
        session.save(update_fields=["state", "version"])

    return session
