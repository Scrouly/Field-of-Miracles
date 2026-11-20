"""Packaging module for exporting and importing Events (Task 17).

Bundles event data (theme, questions, wheels, sectors, rounds, players, prizes, sounds)
into a portable ZIP archive containing manifest.json and media/ assets.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.core.models import (
    Effect,
    Event,
    Player,
    Prize,
    Question,
    Round,
    Sector,
    Sound,
    Tag,
    Theme,
    Wheel,
)


class PackagingError(Exception):
    """Raised when event export or import fails."""


def export_event(event: Event, output_path: str | Path) -> Path:
    """Export an event and all its associated data into a zip archive."""
    out_file = Path(output_path).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)

    media_root = Path(settings.MEDIA_ROOT) if hasattr(settings, "MEDIA_ROOT") else Path("media")

    # 1. Theme
    theme_data = None
    media_files_to_pack: list[tuple[Path, str]] = []  # (abs_path, arcname)

    if event.theme:
        t = event.theme
        theme_data = {
            "name": t.name,
            "colors": t.colors or {},
            "fonts": t.fonts or {},
            "logo": str(t.logo) if t.logo else None,
            "background": str(t.background) if t.background else None,
        }
        if t.logo and (media_root / str(t.logo)).is_file():
            media_files_to_pack.append((media_root / str(t.logo), f"media/{t.logo}"))
        if t.background and (media_root / str(t.background)).is_file():
            media_files_to_pack.append((media_root / str(t.background), f"media/{t.background}"))

    # 2. Effects
    effects_data = []
    seen_effects: set[int] = set()

    # 3. Wheels & Sectors
    wheels_data = []
    seen_wheels: set[int] = set()

    for r in event.rounds.select_related("wheel", "question", "prize").order_by("order"):
        if r.wheel and r.wheel_id not in seen_wheels:
            seen_wheels.add(r.wheel_id)
            w = r.wheel
            sectors_list = []
            for s in w.sectors.select_related("effect").order_by("order"):
                effect_name = None
                if s.effect:
                    effect_name = s.effect.name
                    if s.effect_id not in seen_effects:
                        seen_effects.add(s.effect_id)
                        effects_data.append({"name": s.effect.name, "actions": s.effect.actions})
                sectors_list.append(
                    {
                        "order": s.order,
                        "label": s.label,
                        "color": s.color,
                        "value": s.value,
                        "weight": s.weight,
                        "effect": effect_name,
                    }
                )
            wheels_data.append({"name": w.name, "sectors": sectors_list})

    # Also capture any other effects
    for eff in Effect.objects.all():
        if eff.pk not in seen_effects:
            seen_effects.add(eff.pk)
            effects_data.append({"name": eff.name, "actions": eff.actions})

    # 4. Questions
    questions_data = []
    for r in event.rounds.select_related("question").order_by("order"):
        if r.question:
            q = r.question
            tags = list(q.tags.values_list("name", flat=True))
            questions_data.append(
                {
                    "word": q.word,
                    "text": q.text,
                    "hint": q.hint,
                    "difficulty": q.difficulty,
                    "tags": tags,
                }
            )

    # 5. Prizes
    prizes_data = []
    for p in event.prizes.all().order_by("cost"):
        prizes_data.append(
            {
                "name": p.name,
                "cost": p.cost,
                "image": str(p.image) if p.image else None,
            }
        )
        if p.image and (media_root / str(p.image)).is_file():
            media_files_to_pack.append((media_root / str(p.image), f"media/{p.image}"))

    # 6. Rounds
    rounds_data = []
    for r in event.rounds.select_related("question", "wheel", "prize").order_by("order"):
        rounds_data.append(
            {
                "order": r.order,
                "type": r.type,
                "question_word": r.question.word if r.question else None,
                "wheel_name": r.wheel.name if r.wheel else None,
                "prize_name": r.prize.name if r.prize else None,
                "params": r.params or {},
            }
        )

    # 7. Players
    players_data = []
    for pl in event.players.all().order_by("order"):
        players_data.append(
            {
                "name": pl.name,
                "team": pl.team,
                "order": pl.order,
            }
        )

    # 8. Sounds
    sounds_data = []
    for s in Sound.objects.all():
        sounds_data.append(
            {
                "name": s.name,
                "file": str(s.file),
            }
        )
        if s.file and (media_root / str(s.file)).is_file():
            media_files_to_pack.append((media_root / str(s.file), f"media/{s.file}"))

    manifest = {
        "format_version": "1.0",
        "event": {
            "name": event.name,
            "rules": event.rules or {},
            "is_active": event.is_active,
        },
        "theme": theme_data,
        "effects": effects_data,
        "wheels": wheels_data,
        "questions": questions_data,
        "prizes": prizes_data,
        "rounds": rounds_data,
        "players": players_data,
        "sounds": sounds_data,
    }

    # Write zip file
    with zipfile.ZipFile(out_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for abs_path, arcname in media_files_to_pack:
            if abs_path.is_file():
                zf.write(abs_path, arcname=arcname)

    return out_file


def import_event(zip_path: str | Path, activate: bool = True) -> Event:
    """Import an event and its assets from a zip package."""
    zip_file = Path(zip_path).resolve()
    if not zip_file.is_file():
        raise PackagingError(f"Файл пакета не найден: {zip_file}")

    media_root = Path(settings.MEDIA_ROOT) if hasattr(settings, "MEDIA_ROOT") else Path("media")
    media_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_file, "r") as zf:
        try:
            manifest_bytes = zf.read("manifest.json")
        except KeyError as exc:
            raise PackagingError("В пакете отсутствует manifest.json") from exc

        manifest = json.loads(manifest_bytes.decode("utf-8"))

        # Extract media files
        for item in zf.namelist():
            if item.startswith("media/") and not item.endswith("/"):
                rel_media_path = item[len("media/"):]
                target_file = media_root / rel_media_path
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(item) as src, open(target_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    with transaction.atomic():
        # 1. Effects
        effects_map: dict[str, Effect] = {}
        for eff_data in manifest.get("effects", []):
            eff, _ = Effect.objects.update_or_create(
                name=eff_data["name"],
                defaults={"actions": eff_data.get("actions", [])},
            )
            effects_map[eff.name] = eff

        # 2. Wheels & Sectors
        wheels_map: dict[str, Wheel] = {}
        for w_data in manifest.get("wheels", []):
            w, _ = Wheel.objects.get_or_create(name=w_data["name"])
            w.sectors.all().delete()
            for s_data in w_data.get("sectors", []):
                eff = effects_map.get(s_data.get("effect") or "")
                Sector.objects.create(
                    wheel=w,
                    order=s_data["order"],
                    label=s_data["label"],
                    color=s_data["color"],
                    value=s_data["value"],
                    weight=s_data.get("weight", 1),
                    effect=eff,
                )
            wheels_map[w.name] = w

        # 3. Theme
        theme_obj = None
        theme_data = manifest.get("theme")
        if theme_data:
            theme_obj, _ = Theme.objects.update_or_create(
                name=theme_data["name"],
                defaults={
                    "colors": theme_data.get("colors", {}),
                    "fonts": theme_data.get("fonts", {}),
                    "logo": theme_data.get("logo") or "",
                    "background": theme_data.get("background") or "",
                },
            )

        # 4. Event
        event_info = manifest["event"]
        if activate:
            Event.objects.filter(is_active=True).update(is_active=False)

        event = Event.objects.create(
            name=event_info["name"],
            theme=theme_obj,
            rules=event_info.get("rules", {}),
            is_active=activate or event_info.get("is_active", False),
        )

        # 5. Questions
        questions_map: dict[str, Question] = {}
        for q_data in manifest.get("questions", []):
            q, _ = Question.objects.update_or_create(
                word=q_data["word"],
                defaults={
                    "text": q_data["text"],
                    "hint": q_data.get("hint", ""),
                    "difficulty": q_data.get("difficulty", Question.Difficulty.EASY),
                },
            )
            for tag_name in q_data.get("tags", []):
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                q.tags.add(tag)
            questions_map[q.word] = q

        # 6. Prizes
        prizes_map: dict[str, Prize] = {}
        for p_data in manifest.get("prizes", []):
            p = Prize.objects.create(
                event=event,
                name=p_data["name"],
                cost=p_data["cost"],
                image=p_data.get("image") or "",
            )
            prizes_map[p.name] = p

        # 7. Rounds
        for r_data in manifest.get("rounds", []):
            q = questions_map.get(r_data.get("question_word") or "")
            w = wheels_map.get(r_data.get("wheel_name") or "")
            p = prizes_map.get(r_data.get("prize_name") or "")
            Round.objects.create(
                event=event,
                order=r_data["order"],
                type=r_data.get("type", Round.Type.QUALIFYING),
                question=q,
                wheel=w,
                prize=p,
                params=r_data.get("params", {}),
            )

        # 8. Players
        for pl_data in manifest.get("players", []):
            Player.objects.create(
                event=event,
                name=pl_data["name"],
                team=pl_data.get("team", ""),
                order=pl_data.get("order", 1),
            )

        # 9. Sounds
        for s_data in manifest.get("sounds", []):
            Sound.objects.update_or_create(
                name=s_data["name"],
                defaults={"file": s_data.get("file", "")},
            )

    return event
