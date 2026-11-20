"""Views for the game state API and host/display communication."""

from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.game import services
from apps.game.services import SessionNotFound, VersionConflict
from engine.actions import InvalidAction


@ensure_csrf_cookie
@require_http_methods(["GET"])
def state_api(request: HttpRequest) -> JsonResponse:
    """Return the current game state, or 'no_news' if state has not changed.

    Query parameters:
      - since: optional int version counter.
      - session_id: optional int session primary key.
    """
    since_param = request.GET.get("since")
    since: int | None = None
    if since_param is not None:
        try:
            since = int(since_param)
        except ValueError:
            return JsonResponse(
                {"error": "invalid_parameter", "message": "Параметр 'since' должен быть целым числом"},
                status=400,
            )

    session_id_param = request.GET.get("session_id")
    session_id: int | None = None
    if session_id_param is not None:
        try:
            session_id = int(session_id_param)
        except ValueError:
            return JsonResponse(
                {"error": "invalid_parameter", "message": "Параметр 'session_id' должен быть целым числом"},
                status=400,
            )

    try:
        data: dict[str, Any] = services.get_state_data(session_id=session_id, since=since)
        return JsonResponse(data)
    except SessionNotFound as exc:
        return JsonResponse({"error": "not_found", "message": str(exc)}, status=404)


@require_http_methods(["POST"])
def action_api(request: HttpRequest) -> JsonResponse:
    """Apply an action to the game state with optimistic locking.

    Payload (JSON):
      - expected_version: int (mandatory)
      - action: dict (or action fields directly at top-level)
      - session_id: optional int
    """
    try:
        body: dict[str, Any] = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "invalid_json", "message": "Тело запроса должно быть корректным JSON"},
            status=400,
        )

    if not isinstance(body, dict):
        return JsonResponse(
            {"error": "invalid_payload", "message": "JSON должен быть объектом"},
            status=400,
        )

    if "expected_version" not in body or body["expected_version"] is None:
        return JsonResponse(
            {"error": "missing_expected_version", "message": "Параметр 'expected_version' обязателен"},
            status=400,
        )

    try:
        expected_version = int(body["expected_version"])
    except (ValueError, TypeError):
        return JsonResponse(
            {"error": "invalid_expected_version", "message": "Параметр 'expected_version' должен быть числом"},
            status=400,
        )

    session_id = body.get("session_id")
    if session_id is not None:
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            return JsonResponse(
                {"error": "invalid_session_id", "message": "Параметр 'session_id' должен быть числом"},
                status=400,
            )

    # Support either {"action": {"type": "..."}} or flat {"type": "..."}
    if "action" in body and isinstance(body["action"], dict):
        action_data = body["action"]
    else:
        # Extract action fields without metadata
        action_data = {
            k: v for k, v in body.items() if k not in ("expected_version", "session_id")
        }

    try:
        result = services.apply_action(
            action_data=action_data,
            expected_version=expected_version,
            session_id=session_id,
        )
        return JsonResponse(result, status=200)
    except VersionConflict as exc:
        return JsonResponse(
            {
                "error": "conflict",
                "message": str(exc),
                "current_version": exc.current_version,
                "state": exc.current_state,
            },
            status=409,
        )
    except InvalidAction as exc:
        return JsonResponse(
            {"error": "invalid_action", "message": str(exc)},
            status=400,
        )
    except SessionNotFound as exc:
        return JsonResponse(
            {"error": "not_found", "message": str(exc)},
            status=404,
        )


@ensure_csrf_cookie
@require_http_methods(["GET"])
def display_view(request: HttpRequest):
    """Render the main multiboard display screen."""
    session = services.get_or_create_session()
    context = {
        "session_id": session.pk,
        "event_name": session.event.name,
    }
    return render(request, "display/index.html", context)
