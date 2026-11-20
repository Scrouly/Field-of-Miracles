"""Theme editor, sound trigger bindings, and prize exchange showcase (Task 15).

Supports custom theme palettes, CSS custom property generation for screens,
sound mapping, and prize showcase calculation.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from apps.core.models import Event, GameLog, GameSession, Prize, Sound, Theme

HEX_COLOR_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")

# Pre-packaged themes
DOLOMITE_THEME_COLORS = {
    "bg_main": "#0b132b",
    "bg_card": "#1c2541",
    "bg_card_light": "#243356",
    "color_gold": "#f4c430",
    "color_gold_hover": "#e0a91e",
    "color_text": "#ffffff",
    "color_text_dim": "#a0aec0",
    "color_accent": "#2a9d8f",
}

ANNIVERSARY_THEME_COLORS = {
    "bg_main": "#1a120b",
    "bg_card": "#2a1e17",
    "bg_card_light": "#3e2c22",
    "color_gold": "#ffd700",
    "color_gold_hover": "#e6be00",
    "color_text": "#ffffff",
    "color_text_dim": "#d4b996",
    "color_accent": "#e76f51",
}

HIGH_CONTRAST_THEME_COLORS = {
    "bg_main": "#000000",
    "bg_card": "#111111",
    "bg_card_light": "#222222",
    "color_gold": "#ffdd00",
    "color_gold_hover": "#ffcc00",
    "color_text": "#ffffff",
    "color_text_dim": "#cccccc",
    "color_accent": "#00ffff",
}

THEME_PRESETS = {
    "dolomite": ("Классический Доломит", DOLOMITE_THEME_COLORS),
    "anniversary": ("Юбилейная", ANNIVERSARY_THEME_COLORS),
    "high_contrast": ("Высокая контрастность (для зала)", HIGH_CONTRAST_THEME_COLORS),
}

DEFAULT_SOUND_TRIGGERS = {
    "bankrupt": "bankrupt",
    "gong": "gong",
    "win": "win",
    "miss": "miss",
    "box_game": "box_game",
    "sector_plus": "sector_plus",
    "timer_start": "timer_start",
    "letter_open": "letter_open",
}


def get_or_create_default_theme() -> Theme:
    """Ensure a default Dolomite theme exists."""
    theme, created = Theme.objects.get_or_create(
        name="Доломит — Классическая",
        defaults={
            "colors": DOLOMITE_THEME_COLORS,
            "fonts": {"heading": "sans-serif", "body": "sans-serif"},
        },
    )
    return theme


def generate_theme_css(theme: Theme | None) -> str:
    """Generate CSS :root variables from the given theme."""
    colors = dict(DOLOMITE_THEME_COLORS)
    if theme and isinstance(theme.colors, dict):
        for k, v in theme.colors.items():
            if isinstance(v, str) and HEX_COLOR_REGEX.match(v):
                colors[k] = v

    css_vars = []
    for key, val in colors.items():
        css_name = "--" + key.replace("_", "-")
        css_vars.append(f"  {css_name}: {val};")

    css_content = ":root {\n" + "\n".join(css_vars) + "\n}\n"
    return css_content


def update_theme_colors(theme: Theme, new_colors: dict[str, str]) -> Theme:
    """Validate and update theme color variables."""
    cleaned = dict(theme.colors or DOLOMITE_THEME_COLORS)
    for k, v in new_colors.items():
        if isinstance(v, str) and HEX_COLOR_REGEX.match(v.strip()):
            cleaned[k] = v.strip().lower()

    theme.colors = cleaned
    theme.save(update_fields=["colors"])
    return theme


def get_prize_showcase(event: Event, player_score: int) -> dict[str, Any]:
    """Calculate prize showcase for the given player score.

    Categorizes prizes into affordable and unaffordable with missing point calculations.
    """
    prizes = event.prizes.all().order_by("cost")
    showcase = []

    for p in prizes:
        can_afford = player_score >= p.cost
        missing = max(0, p.cost - player_score)
        showcase.append(
            {
                "id": p.pk,
                "name": p.name,
                "cost": p.cost,
                "image_url": p.image.url if p.image else None,
                "can_afford": can_afford,
                "missing_points": missing,
            }
        )

    return {
        "player_score": player_score,
        "total_prizes": len(showcase),
        "affordable_count": sum(1 for item in showcase if item["can_afford"]),
        "prizes": showcase,
    }


def exchange_prize(
    session: GameSession,
    prize: Prize,
    player_index: int | None = None,
) -> dict[str, Any]:
    """Exchange player score points for a selected prize.

    Deducts cost, records GameLog, and increments session version.
    """
    with transaction.atomic():
        locked_session = GameSession.objects.select_for_update().get(pk=session.pk)
        state_dict = dict(locked_session.state)

        scores = list(state_dict.get("scores", []))
        p_idx = player_index if player_index is not None else state_dict.get("current_player", 0)

        if p_idx < 0 or p_idx >= len(scores):
            raise ValueError(f"Некорректный индекс игрока: {p_idx}")

        current_score = scores[p_idx]
        if current_score < prize.cost:
            raise ValueError(f"Недостаточно очков для обмена на «{prize.name}» (нужно {prize.cost}, есть {current_score})")

        new_score = current_score - prize.cost
        scores[p_idx] = new_score
        state_dict["scores"] = scores
        state_dict["pending_modal"] = f"prize_claimed:{prize.name}"
        state_dict["pending_sound"] = "win"

        new_version = locked_session.version + 1
        state_dict["version"] = new_version
        locked_session.state = state_dict
        locked_session.version = new_version
        locked_session.save(update_fields=["state", "version"])

        GameLog.objects.create(
            session=locked_session,
            number=new_version,
            action="EXCHANGE_PRIZE",
            data={
                "prize_id": prize.pk,
                "prize_name": prize.name,
                "cost": prize.cost,
                "player_index": p_idx,
                "remaining_score": new_score,
            },
        )

        return {
            "status": "ok",
            "prize": prize.name,
            "cost": prize.cost,
            "player_index": p_idx,
            "remaining_score": new_score,
            "version": new_version,
        }
