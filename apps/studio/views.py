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

from apps.core.models import Effect, Sector, Wheel

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
