"""Views and APIs for Studio management panel."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from django.core.validators import RegexValidator
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from apps.core.models import Effect, Event, Prize, Question, Round, Sector, Sound, Theme, Wheel
from apps.studio import scenario, theme_editor
from apps.studio.scenario import ScenarioError

STUDIO_PIN = os.environ.get("STUDIO_PIN", os.environ.get("HOST_PIN", "1931"))
HEX_COLOR_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Default Dolomite sectors if brand new wheel is created with defaults
DEFAULT_SECTOR_SPECS = [
    {"label": "100", "value": 100, "color": "#1f4e5b", "weight": 1},
    {"label": "300", "value": 300, "color": "#243356", "weight": 1},
    {"label": "150", "value": 150, "color": "#162447", "weight": 1},
    {"label": "200", "value": 200, "color": "#2a9d8f", "weight": 1},
    {"label": "500", "value": 500, "color": "#d97706", "weight": 1},
    {"label": "100", "value": 100, "color": "#1f4e5b", "weight": 1},
    {"label": "250", "value": 250, "color": "#243356", "weight": 1},
    {"label": "400", "value": 400, "color": "#3b82f6", "weight": 1},
    {"label": "150", "value": 150, "color": "#162447", "weight": 1},
    {"label": "200", "value": 200, "color": "#2a9d8f", "weight": 1},
    {"label": "600", "value": 600, "color": "#8b5cf6", "weight": 1},
    {"label": "350", "value": 350, "color": "#243356", "weight": 1},
    {"label": "100", "value": 100, "color": "#1f4e5b", "weight": 1},
    {"label": "300", "value": 300, "color": "#162447", "weight": 1},
    {"label": "750", "value": 750, "color": "#ef4444", "weight": 1},
    {"label": "250", "value": 250, "color": "#2a9d8f", "weight": 1},
]


def is_studio_authenticated(request: HttpRequest) -> bool:
    """Check if the session or request has studio access."""
    if request.user.is_authenticated and request.user.is_staff:
        return True

    pin = request.GET.get("pin") or request.POST.get("pin")
    if pin and pin == STUDIO_PIN:
        request.session["studio_authenticated"] = True
        return True

    auth_header = request.headers.get("X-Studio-PIN")
    if auth_header and auth_header == STUDIO_PIN:
        request.session["studio_authenticated"] = True
        return True

    return bool(request.session.get("studio_authenticated"))


def studio_login_view(request: HttpRequest) -> HttpResponse:
    """PIN entry screen for Studio."""
    error = ""
    if request.method == "POST":
        pin = request.POST.get("pin", "").strip()
        if pin == STUDIO_PIN:
            request.session["studio_authenticated"] = True
            next_url = request.GET.get("next") or request.POST.get("next") or "/studio/wheels/"
            return redirect(next_url)
        error = "Неверный PIN-код"

    return render(request, "studio/login.html", {"error": error})


def studio_logout_view(request: HttpRequest) -> HttpResponse:
    """Clear studio session authentication."""
    request.session.pop("studio_authenticated", None)
    return redirect("studio:login")


@ensure_csrf_cookie
def wheel_editor_view(request: HttpRequest, wheel_id: int | None = None) -> HttpResponse:
    """Render the Wheel Editor interface in Studio."""
    if not is_studio_authenticated(request):
        next_param = f"?next={request.path}"
        return redirect(f"/studio/login/{next_param}")

    wheels = Wheel.objects.all().order_by("name")
    if not wheels.exists():
        wheel = Wheel.objects.create(name="Основной барабан")
        # Initialize with standard sectors
        for idx, spec in enumerate(DEFAULT_SECTOR_SPECS):
            Sector.objects.create(
                wheel=wheel,
                order=idx,
                label=spec["label"],
                color=spec["color"],
                value=spec["value"],
                weight=spec["weight"],
            )
        wheels = Wheel.objects.all().order_by("name")

    if wheel_id:
        current_wheel = get_object_or_404(Wheel, pk=wheel_id)
    else:
        current_wheel = wheels.first()

    effects = Effect.objects.all().order_by("name")

    context = {
        "wheels": wheels,
        "current_wheel": current_wheel,
        "effects": effects,
    }
    return render(request, "studio/wheel_editor.html", context)


# ---------------------------------------------------------------------------
# REST API endpoints for Wheel & Sector management
# ---------------------------------------------------------------------------


def _serialize_sector(sector: Sector) -> dict[str, Any]:
    return {
        "id": sector.pk,
        "order": sector.order,
        "label": sector.label,
        "color": sector.color,
        "value": sector.value,
        "weight": sector.weight,
        "effect_id": sector.effect_id,
        "effect_name": sector.effect.name if sector.effect else None,
    }


def _serialize_wheel(wheel: Wheel) -> dict[str, Any]:
    sectors = [_serialize_sector(s) for s in wheel.sectors.all().order_by("order")]
    return {
        "id": wheel.pk,
        "name": wheel.name,
        "sector_count": len(sectors),
        "sectors": sectors,
    }


@require_http_methods(["GET", "POST"])
def wheel_list_api(request: HttpRequest) -> JsonResponse:
    """List wheels or create a new wheel."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    if request.method == "GET":
        wheels = [
            {"id": w.pk, "name": w.name, "sector_count": w.sectors.count()}
            for w in Wheel.objects.all().order_by("name")
        ]
        return JsonResponse({"wheels": wheels})

    # POST: create wheel
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    name = data.get("name", "").strip() or "Новый барабан"
    with transaction.atomic():
        wheel = Wheel.objects.create(name=name)
        # Populate with standard default 16 sectors if requested or by default
        with_defaults = data.get("with_defaults", True)
        if with_defaults:
            for idx, spec in enumerate(DEFAULT_SECTOR_SPECS):
                Sector.objects.create(
                    wheel=wheel,
                    order=idx,
                    label=spec["label"],
                    color=spec["color"],
                    value=spec["value"],
                    weight=spec["weight"],
                )

    return JsonResponse({"status": "ok", "wheel": _serialize_wheel(wheel)}, status=201)


@require_http_methods(["GET", "PUT", "DELETE"])
def wheel_detail_api(request: HttpRequest, wheel_id: int) -> JsonResponse:
    """Get, rename or delete a specific wheel."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    try:
        wheel = Wheel.objects.prefetch_related("sectors__effect").get(pk=wheel_id)
    except Wheel.DoesNotExist:
        return JsonResponse({"error": "not_found", "message": "Барабан не найден"}, status=404)

    if request.method == "GET":
        effects = [{"id": e.pk, "name": e.name} for e in Effect.objects.all().order_by("name")]
        return JsonResponse(
            {
                "status": "ok",
                "wheel": _serialize_wheel(wheel),
                "effects": effects,
            }
        )

    if request.method == "DELETE":
        wheel.delete()
        return JsonResponse({"status": "ok", "deleted": wheel_id})

    # PUT: rename wheel
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "invalid_name", "message": "Название не может быть пустым"}, status=400)

    wheel.name = name
    wheel.save(update_fields=["name"])
    return JsonResponse({"status": "ok", "wheel": _serialize_wheel(wheel)})


@require_http_methods(["POST", "PUT"])
def wheel_sectors_api(request: HttpRequest, wheel_id: int) -> JsonResponse:
    """Save or update sectors for a wheel atomically."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    sectors_data = data.get("sectors")
    if not isinstance(sectors_data, list):
        return JsonResponse(
            {"error": "invalid_payload", "message": "'sectors' должен быть массивом"},
            status=400,
        )

    if len(sectors_data) < 2:
        return JsonResponse(
            {"error": "too_few_sectors", "message": "Барабан должен содержать как минимум 2 сектора"},
            status=400,
        )

    # Validate each sector
    validated_sectors = []
    for idx, item in enumerate(sectors_data):
        label = str(item.get("label", "")).strip()
        if not label:
            return JsonResponse(
                {"error": "invalid_sector", "message": f"Сектор #{idx + 1}: подпись не может быть пустой"},
                status=400,
            )
        if len(label) > 30:
            return JsonResponse(
                {"error": "invalid_sector", "message": f"Сектор #{idx + 1}: подпись превышает 30 символов"},
                status=400,
            )

        color = str(item.get("color", "#cccccc")).strip().lower()
        if not HEX_COLOR_REGEX.match(color):
            color = "#cccccc"

        try:
            value = int(item.get("value", 0))
        except (ValueError, TypeError):
            value = 0

        try:
            weight = int(item.get("weight", 1))
            if weight < 1:
                weight = 1
        except (ValueError, TypeError):
            weight = 1

        effect_id = item.get("effect_id")
        if effect_id:
            try:
                effect_id = int(effect_id)
                if not Effect.objects.filter(pk=effect_id).exists():
                    effect_id = None
            except (ValueError, TypeError):
                effect_id = None
        else:
            effect_id = None

        validated_sectors.append(
            {
                "order": idx,
                "label": label,
                "color": color,
                "value": value,
                "weight": weight,
                "effect_id": effect_id,
            }
        )

    with transaction.atomic():
        wheel = get_object_or_404(Wheel.objects.select_for_update(), pk=wheel_id)

        # Update name if provided
        new_name = data.get("name")
        if new_name and isinstance(new_name, str) and new_name.strip():
            wheel.name = new_name.strip()
            wheel.save(update_fields=["name"])

        # Safely replace sectors atomically
        wheel.sectors.all().delete()
        new_sectors = [
            Sector(
                wheel=wheel,
                order=item["order"],
                label=item["label"],
                color=item["color"],
                value=item["value"],
                weight=item["weight"],
                effect_id=item["effect_id"],
            )
            for item in validated_sectors
        ]
        Sector.objects.bulk_create(new_sectors)

    # Return refreshed wheel
    wheel.refresh_from_db()
    return JsonResponse(
        {
            "status": "ok",
            "message": "Барабан успешно сохранён",
            "wheel": _serialize_wheel(wheel),
        }
    )


# ---------------------------------------------------------------------------
# Scenario & Round Management (Task 12)
# ---------------------------------------------------------------------------


def _serialize_round(r: Round) -> dict[str, Any]:
    return {
        "id": r.pk,
        "order": r.order,
        "type": r.type,
        "type_display": r.get_type_display(),
        "question_id": r.question_id,
        "question_word": r.question.word if r.question else None,
        "question_text": r.question.text if r.question else None,
        "wheel_id": r.wheel_id,
        "wheel_name": r.wheel.name if r.wheel else None,
        "prize_id": r.prize_id,
        "prize_name": r.prize.name if r.prize else None,
        "params": r.params or {},
    }


@ensure_csrf_cookie
def scenario_view(request: HttpRequest, event_id: int | None = None) -> HttpResponse:
    """Render the Event Scenario & Round sequencing interface."""
    if not is_studio_authenticated(request):
        next_param = f"?next={request.path}"
        return redirect(f"/studio/login/{next_param}")

    events = Event.objects.all().order_by("-is_active", "name")
    if not events.exists():
        event = Event.objects.create(name="Корпоратив ОАО «Доломит»", is_active=True)
        events = Event.objects.all()
    else:
        if event_id:
            event = get_object_or_404(Event, pk=event_id)
        else:
            event = events.filter(is_active=True).first() or events.first()

    questions = Question.objects.all().order_by("word")
    wheels = Wheel.objects.all().order_by("name")
    prizes = Prize.objects.filter(event=event).order_by("cost")

    context = {
        "events": events,
        "current_event": event,
        "questions": questions,
        "wheels": wheels,
        "prizes": prizes,
    }
    return render(request, "studio/scenario.html", context)


@require_http_methods(["GET", "POST"])
def event_rounds_api(request: HttpRequest, event_id: int) -> JsonResponse:
    """List rounds for an event or create a new round."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    event = get_object_or_404(Event, pk=event_id)

    if request.method == "GET":
        rounds = scenario.get_event_rounds(event)
        questions = [
            {"id": q.pk, "word": q.word, "text": q.text, "difficulty": q.get_difficulty_display()}
            for q in Question.objects.all().order_by("word")
        ]
        wheels = [
            {"id": w.pk, "name": w.name, "sector_count": w.sectors.count()}
            for w in Wheel.objects.all().order_by("name")
        ]
        prizes = [
            {"id": p.pk, "name": p.name, "cost": p.cost}
            for p in Prize.objects.filter(event=event).order_by("cost")
        ]
        return JsonResponse(
            {
                "status": "ok",
                "event": {"id": event.pk, "name": event.name},
                "rounds": [_serialize_round(r) for r in rounds],
                "questions": questions,
                "wheels": wheels,
                "prizes": prizes,
            }
        )

    # POST: create a new round
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    round_type = data.get("type", Round.Type.QUALIFYING)
    if round_type not in Round.Type.values:
        round_type = Round.Type.QUALIFYING

    question_id = data.get("question_id")
    question = Question.objects.filter(pk=question_id).first() if question_id else None

    wheel_id = data.get("wheel_id")
    wheel = Wheel.objects.filter(pk=wheel_id).first() if wheel_id else None

    prize_id = data.get("prize_id")
    prize = Prize.objects.filter(pk=prize_id, event=event).first() if prize_id else None

    params = data.get("params", {})
    if not isinstance(params, dict):
        params = {}

    new_round = scenario.create_round(
        event=event,
        round_type=round_type,
        question=question,
        wheel=wheel,
        prize=prize,
        params=params,
    )

    return JsonResponse({"status": "ok", "round": _serialize_round(new_round)}, status=201)


@require_http_methods(["POST"])
def event_rounds_reorder_api(request: HttpRequest, event_id: int) -> JsonResponse:
    """Safely reorder rounds for an event without duplicate order errors."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    event = get_object_or_404(Event, pk=event_id)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    round_ids = data.get("round_ids")
    if not isinstance(round_ids, list):
        return JsonResponse(
            {"error": "invalid_payload", "message": "'round_ids' должен быть списком чисел"},
            status=400,
        )

    try:
        updated_rounds = scenario.reorder_rounds(event=event, round_ids=round_ids)
        return JsonResponse(
            {
                "status": "ok",
                "message": "Порядок туров успешно сохранён",
                "rounds": [_serialize_round(r) for r in updated_rounds],
            }
        )
    except ScenarioError as exc:
        return JsonResponse({"error": "reorder_failed", "message": str(exc)}, status=400)


@require_http_methods(["PUT", "DELETE"])
def round_detail_api(request: HttpRequest, round_id: int) -> JsonResponse:
    """Update or delete a specific round."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    round_obj = get_object_or_404(Round, pk=round_id)

    if request.method == "DELETE":
        scenario.delete_round(round_obj)
        return JsonResponse({"status": "ok", "deleted": round_id})

    # PUT: update round bindings
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    updated_round = scenario.update_round(
        round_obj=round_obj,
        round_type=data.get("type"),
        question_id=data.get("question_id"),
        wheel_id=data.get("wheel_id"),
        prize_id=data.get("prize_id"),
        params=data.get("params"),
    )

    return JsonResponse(
        {
            "status": "ok",
            "message": "Параметры тура обновлены",
            "round": _serialize_round(updated_round),
        }
    )


# ---------------------------------------------------------------------------
# Theme, Sounds, and Prize Showcase (Task 15)
# ---------------------------------------------------------------------------


@ensure_csrf_cookie
def theme_editor_view(request: HttpRequest, theme_id: int | None = None) -> HttpResponse:
    """Render Theme, Sound triggers, and Prize Showcase studio editor."""
    if not is_studio_authenticated(request):
        next_param = f"?next={request.path}"
        return redirect(f"/studio/login/{next_param}")

    themes = Theme.objects.all().order_by("name")
    if not themes.exists():
        theme = theme_editor.get_or_create_default_theme()
        themes = Theme.objects.all()
    else:
        theme = get_object_or_404(Theme, pk=theme_id) if theme_id else themes.first()

    event = Event.objects.filter(is_active=True).first() or Event.objects.first()
    prizes = event.prizes.all().order_by("cost") if event else Prize.objects.none()
    sounds = Sound.objects.all().order_by("name")

    context = {
        "themes": themes,
        "current_theme": theme,
        "presets": theme_editor.THEME_PRESETS,
        "prizes": prizes,
        "sounds": sounds,
        "current_event": event,
    }
    return render(request, "studio/theme_editor.html", context)


@require_http_methods(["GET", "POST"])
def api_theme_detail(request: HttpRequest, theme_id: int) -> JsonResponse:
    """Retrieve or update theme colors and parameters."""
    if not is_studio_authenticated(request):
        return JsonResponse({"error": "unauthorized", "message": "Требуется PIN-код"}, status=401)

    theme = get_object_or_404(Theme, pk=theme_id)

    if request.method == "GET":
        return JsonResponse(
            {
                "status": "ok",
                "theme": {
                    "id": theme.pk,
                    "name": theme.name,
                    "colors": theme.colors or theme_editor.DOLOMITE_THEME_COLORS,
                    "fonts": theme.fonts or {},
                },
                "presets": theme_editor.THEME_PRESETS,
            }
        )

    # POST: update colors
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_json"}, status=400)

    colors = data.get("colors")
    if not isinstance(colors, dict):
        return JsonResponse({"error": "invalid_payload", "message": "'colors' должен быть объектом"}, status=400)

    theme_editor.update_theme_colors(theme, colors)

    return JsonResponse(
        {
            "status": "ok",
            "message": "Тема успешно сохранена",
            "theme": {
                "id": theme.pk,
                "name": theme.name,
                "colors": theme.colors,
            },
        }
    )
