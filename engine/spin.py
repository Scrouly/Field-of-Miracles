"""Wheel and spin logic (Task 7).

Pure Python: no database or Django dependency.
The final sector is decided deterministically on the server via ``choose_sector()``,
and the frontend canvas animation visually leads to that predetermined sector.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class SectorInfo:
    """Lightweight representation of a wheel sector."""

    label: str
    value: int
    color: str = "#1e90ff"
    weight: int = 1
    effect: str | None = None


def choose_sector(
    sectors: Sequence[SectorInfo | dict[str, Any] | int],
    rng: random.Random | None = None,
) -> int:
    """Select a sector index according to sector weights.

    Parameters:
      - sectors: sequence of SectorInfo, dictionaries with 'weight', or weight integers.
      - rng: optional random.Random instance for seeded/deterministic selection.

    Returns:
      Index of the chosen sector: ``0 <= index < len(sectors)``.

    Raises:
      ValueError: if sectors is empty or all weights are <= 0.
    """
    if not sectors:
        raise ValueError("Колесо должно содержать хотя бы один сектор")

    if rng is None:
        rng = random.Random()

    weights: list[int] = []
    for s in sectors:
        if isinstance(s, SectorInfo):
            w = s.weight
        elif isinstance(s, dict):
            w = int(s.get("weight", 1))
        elif isinstance(s, (int, float)):
            w = int(s)
        else:
            w = getattr(s, "weight", 1)

        weights.append(max(0, int(w)))

    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Суммарный вес секторов должен быть больше 0")

    # Weighted random selection
    chosen_indices = rng.choices(range(len(sectors)), weights=weights, k=1)
    return chosen_indices[0]
