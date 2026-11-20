"""Views for the game state API and host/display communication."""

from __future__ import annotations

import json
import os
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.core.models import Event, GameSession, Prize, Theme
from apps.game import services
from apps.game.services import SessionNotFound, VersionConflict
from apps.studio import theme_editor
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


HOST_PIN = os.environ.get("HOST_PIN", "1931")


@ensure_csrf_cookie
def host_view(request: HttpRequest):
    """Render the host control panel (/host/) with PIN protection."""
    error = ""
    # Check if PIN provided via GET or POST
    pin = request.POST.get("pin") or request.GET.get("pin")
    if pin is not None:
        if pin == HOST_PIN:
            request.session["host_authenticated"] = True
        else:
            error = "Неверный PIN-код"

    if not request.session.get("host_authenticated"):
        return render(request, "host/login.html", {"error": error})

    session = services.get_or_create_session()
    context = {
        "session_id": session.pk,
        "event_name": session.event.name,
    }
    return render(request, "host/host.html", context)


@require_http_methods(["GET"])
def logs_api(request: HttpRequest) -> JsonResponse:
    """Return the recent action logs for the session."""
    session_id_param = request.GET.get("session_id")
    session_id = None
    if session_id_param is not None:
        try:
            session_id = int(session_id_param)
        except ValueError:
            return JsonResponse({"error": "invalid_session_id"}, status=400)

    logs = services.get_session_logs(session_id=session_id)
    return JsonResponse({"status": "ok", "logs": logs})


@require_http_methods(["GET"])
def theme_css_view(request: HttpRequest) -> HttpResponse:
    """Serve dynamic CSS custom properties based on active event's theme (Task 15)."""
    theme_id = request.GET.get("theme_id")
    theme = None
    if theme_id:
        theme = Theme.objects.filter(pk=theme_id).first()

    if not theme:
        event = Event.objects.filter(is_active=True).select_related("theme").first() or Event.objects.first()
        if event and event.theme:
            theme = event.theme
        else:
            theme = Theme.objects.first() or theme_editor.get_or_create_default_theme()

    css_code = theme_editor.generate_theme_css(theme)
    return HttpResponse(css_code, content_type="text/css")


@require_http_methods(["GET"])
def prize_showcase_api(request: HttpRequest) -> JsonResponse:
    """Return prize showcase and affordability calculation for a player (Task 15)."""
    session = services.get_or_create_session()
    state_dict = dict(session.state)
    scores = state_dict.get("scores", [])
    current_player = state_dict.get("current_player", 0)

    score_param = request.GET.get("score")
    if score_param is not None:
        try:
            player_score = int(score_param)
        except ValueError:
            player_score = 0
    else:
        player_score = scores[current_player] if (0 <= current_player < len(scores)) else 0

    showcase_data = theme_editor.get_prize_showcase(session.event, player_score)
    return JsonResponse({"status": "ok", **showcase_data})


@require_http_methods(["POST"])
def prize_exchange_api(request: HttpRequest) -> JsonResponse:
    """Exchange player score points for a selected prize (Task 15)."""
    session = services.get_or_create_session()
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    prize_id = body.get("prize_id")
    if not prize_id:
        return JsonResponse({"error": "missing_prize_id", "message": "Параметр 'prize_id' обязателен"}, status=400)

    prize = Prize.objects.filter(pk=prize_id, event=session.event).first()
    if not prize:
        return JsonResponse({"error": "not_found", "message": "Приз не найден в данном мероприятии"}, status=404)

    player_index = body.get("player_index")
    try:
        result = theme_editor.exchange_prize(session, prize, player_index)
        return JsonResponse(result, status=200)
    except ValueError as exc:
        return JsonResponse({"error": "exchange_failed", "message": str(exc)}, status=400)


@ensure_csrf_cookie
@require_http_methods(["GET"])
def game_rounds_api(request: HttpRequest) -> JsonResponse:
    """Return all rounds of the active session's event."""
    session = services.get_or_create_session()
    rounds = session.event.rounds.select_related("question").order_by("order")
    result = []
    for r in rounds:
        players = r.params.get("players") if r.params else []
        result.append({
            "id": r.pk,
            "order": r.order,
            "type": r.type,
            "word": r.question.word if r.question else "",
            "question": r.question.text if r.question else "",
            "hint": r.question.hint if r.question else "",
            "players": players,
        })
    return JsonResponse({"rounds": result, "active_word": session.state.get("word")})


@ensure_csrf_cookie
@require_http_methods(["POST"])
def reset_test_game_api(request: HttpRequest) -> JsonResponse:
    """Reset the game session to Tour 1 with clean state."""
    session = services.reset_test_game()
    return JsonResponse({
        "status": "ok",
        "message": "Тестовая игра успешно сброшена и готова к проверке",
        "session_id": session.pk,
        "word": session.state.get("word"),
        "players": session.state.get("players"),
        "version": session.version,
    })
