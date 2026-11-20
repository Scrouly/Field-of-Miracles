"""Business logic for Event scenarios and round scheduling (Task 12).

Manages rounds, their sequence, question/wheel/prize bindings,
and safe atomic reordering that strictly prevents duplicate order constraint errors.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.core.models import Event, Prize, Question, Round, Wheel


class ScenarioError(Exception):
    """Base exception for scenario manipulation errors."""


def get_event_rounds(event: Event) -> list[Round]:
    """Return all rounds for an event ordered by `order`."""
    return list(
        event.rounds.select_related("question", "wheel", "prize").order_by("order")
    )


def reorder_rounds(event: Event | int, round_ids: list[int]) -> list[Round]:
    """Reorder rounds for an event according to round_ids sequence.

    Uses a two-phase update in an atomic transaction to prevent
    `unique_round_order_in_event` constraint collisions:
      1. Assign temporary large offset orders (10000 + i)
      2. Assign final sequential 1-based orders (1, 2, ... N)

    Raises ScenarioError if round IDs are invalid or belong to another event.
    """
    if isinstance(event, int):
        event_obj = Event.objects.get(pk=event)
    else:
        event_obj = event

    with transaction.atomic():
        rounds = list(Round.objects.select_for_update().filter(event=event_obj))
        round_map = {r.pk: r for r in rounds}

        if len(round_ids) != len(rounds) or set(round_ids) != set(round_map.keys()):
            raise ScenarioError("Список ID туров должен в точности соответствовать турам данного мероприятия")

        # Phase 1: Set temporary high offsets to avoid unique constraint collision
        for idx, rid in enumerate(round_ids):
            Round.objects.filter(pk=rid).update(order=10000 + idx)

        # Phase 2: Set final sequential orders 1..N
        for idx, rid in enumerate(round_ids):
            Round.objects.filter(pk=rid).update(order=idx + 1)

    return list(Round.objects.filter(event=event_obj).select_related("question", "wheel", "prize").order_by("order"))


def create_round(
    event: Event,
    round_type: str = Round.Type.QUALIFYING,
    question: Question | None = None,
    wheel: Wheel | None = None,
    prize: Prize | None = None,
    params: dict[str, Any] | None = None,
) -> Round:
    """Create a new round at the end of the event's sequence."""
    with transaction.atomic():
        max_order = (
            Round.objects.filter(event=event).aggregate(Max("order"))["order__max"] or 0
        )
        new_order = max_order + 1
        return Round.objects.create(
            event=event,
            order=new_order,
            type=round_type,
            question=question,
            wheel=wheel,
            prize=prize,
            params=params or {},
        )


def update_round(
    round_obj: Round,
    round_type: str | None = None,
    question_id: int | None = None,
    wheel_id: int | None = None,
    prize_id: int | None = None,
    params: dict[str, Any] | None = None,
) -> Round:
    """Update round bindings."""
    update_fields = []
    if round_type is not None and round_type in Round.Type.values:
        round_obj.type = round_type
        update_fields.append("type")

    if question_id is not None:
        round_obj.question_id = question_id if question_id > 0 else None
        update_fields.append("question")

    if wheel_id is not None:
        round_obj.wheel_id = wheel_id if wheel_id > 0 else None
        update_fields.append("wheel")

    if prize_id is not None:
        round_obj.prize_id = prize_id if prize_id > 0 else None
        update_fields.append("prize")

    if params is not None and isinstance(params, dict):
        round_obj.params = params
        update_fields.append("params")

    if update_fields:
        round_obj.save(update_fields=update_fields)

    return round_obj


def delete_round(round_obj: Round) -> None:
    """Delete a round and compact orders of remaining rounds to 1..N."""
    event = round_obj.event
    with transaction.atomic():
        round_obj.delete()
        remaining = list(Round.objects.filter(event=event).order_by("order"))
        for idx, r in enumerate(remaining):
            Round.objects.filter(pk=r.pk).update(order=10000 + idx)
        for idx, r in enumerate(remaining):
            Round.objects.filter(pk=r.pk).update(order=idx + 1)
