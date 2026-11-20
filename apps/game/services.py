"""Game service layer.

Coordinates GameSession persistence, optimistic locking with versioning,
GameLog journaling, and pure engine transitions.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from django.db import transaction

from apps.core.defaults import default_rules
from apps.core.models import Event, GameLog, GameSession, Theme
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

    players = list(
        event.players.order_by("order").values_list("name", flat=True)
    )
    if not players:
        players = ["Игрок 1", "Игрок 2", "Игрок 3"]

    rules = event.rules or {}
    scoring = rules.get("scoring", "per_occurrence")
    word_bonus = rules.get("word_bonus", 0)

    return new_game(
        word=word,
        players=players,
        scoring=scoring,
        word_bonus=word_bonus,
        sector_value=100,
        question=question_text,
        hint=hint,
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
    return {
        **state_dict,
        "status": "ok",
        "changed": True,
        "version": session.version,
        "session_id": session.pk,
        "state": state_dict,
    }


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

        action: Action = action_from_dict(action_data)
        current_state: GameState = dict_to_state(session.state)

        new_state: GameState = engine_apply(current_state, action)

        # Apply sector effect if SPIN_RESULT has an associated Effect in DB
        if action.type == "SPIN_RESULT" and action.sector_index >= 0:
            round_obj = (
                session.event.rounds.select_related("wheel")
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
        action = action_from_dict(log.data)
        current_state = engine_apply(current_state, action)

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
