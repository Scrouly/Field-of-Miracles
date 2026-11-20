"""Tests for the wheel spinning and sector selection logic (Task 7).

Covers:
  1. choose_sector returns an index strictly within [0, len(sectors) - 1].
  2. Single-sector wheel always returns 0.
  3. Empty wheel or zero-sum weights raise ValueError.
  4. Seeded RNG produces deterministic, reproducible results.
  5. Weighted distribution matches weights within statistical tolerance.
  6. Supports SectorInfo, dict, or integer weight formats.
  7. Engine actions START_SPIN and SPIN_RESULT transition phases and bump versions.
"""

from __future__ import annotations

import random
import pytest

from engine.actions import (
    InvalidAction,
    apply,
    spin_result,
    start_spin,
)
from engine.spin import SectorInfo, choose_sector
from engine.state import new_game


class TestChooseSector:
    def test_single_sector_always_returns_zero(self):
        sectors = [SectorInfo(label="100", value=100, weight=1)]
        assert choose_sector(sectors) == 0

    def test_result_always_in_range(self):
        # 16-20 sectors as required by specification
        for count in (16, 18, 20):
            sectors = [
                SectorInfo(label=str(i * 50), value=i * 50, weight=1)
                for i in range(count)
            ]
            for _ in range(50):
                idx = choose_sector(sectors)
                assert 0 <= idx < count

    def test_empty_wheel_raises_value_error(self):
        with pytest.raises(ValueError, match="хотя бы один сектор"):
            choose_sector([])

    def test_zero_total_weight_raises_value_error(self):
        sectors = [
            SectorInfo(label="0", value=0, weight=0),
            SectorInfo(label="0", value=0, weight=0),
        ]
        with pytest.raises(ValueError, match="больше 0"):
            choose_sector(sectors)

    def test_deterministic_with_seeded_rng(self):
        sectors = [
            SectorInfo(label=str(i * 100), value=i * 100, weight=i + 1)
            for i in range(16)
        ]
        rng1 = random.Random(42)
        res1 = [choose_sector(sectors, rng=rng1) for _ in range(20)]

        rng2 = random.Random(42)
        res2 = [choose_sector(sectors, rng=rng2) for _ in range(20)]

        assert res1 == res2

    def test_weighted_distribution_matches_weights(self):
        """Distribution matches weights: weight 3 vs weight 1 -> ~75% vs ~25%."""
        sectors = [
            SectorInfo(label="A", value=100, weight=1),
            SectorInfo(label="B", value=300, weight=3),
        ]
        rng = random.Random(12345)
        counts = {0: 0, 1: 0}
        trials = 10000

        for _ in range(trials):
            idx = choose_sector(sectors, rng=rng)
            counts[idx] += 1

        freq_0 = counts[0] / trials
        freq_1 = counts[1] / trials

        # Expected: 25% and 75% (+- 2%)
        assert 0.23 <= freq_0 <= 0.27
        assert 0.73 <= freq_1 <= 0.77

    def test_zero_weight_sector_never_chosen(self):
        sectors = [
            SectorInfo(label="Never", value=0, weight=0),
            SectorInfo(label="Always", value=500, weight=10),
        ]
        rng = random.Random(999)
        for _ in range(100):
            assert choose_sector(sectors, rng=rng) == 1

    def test_supports_dict_format(self):
        sectors = [
            {"label": "100", "value": 100, "weight": 5},
            {"label": "200", "value": 200, "weight": 5},
        ]
        idx = choose_sector(sectors, rng=random.Random(1))
        assert idx in (0, 1)

    def test_supports_int_weights_directly(self):
        weights = [1, 2, 3, 4]
        idx = choose_sector(weights, rng=random.Random(1))
        assert 0 <= idx < 4


class TestSpinActions:
    def test_start_spin_transitions_to_spinning(self):
        state = new_game(word="ДОЛОМИТ", players=["Анна"])
        assert state.phase == "await_letter"

        new_state = apply(state, start_spin())
        assert new_state.phase == "spinning"
        assert new_state.version == state.version + 1

    def test_spin_result_sets_sector_and_returns_to_await_letter(self):
        state = new_game(word="ДОЛОМИТ", players=["Анна"])
        state = apply(state, start_spin())
        assert state.phase == "spinning"

        new_state = apply(state, spin_result(sector_index=5, sector_value=350))
        assert new_state.phase == "await_letter"
        assert new_state.sector_index == 5
        assert new_state.sector_value == 350
        assert new_state.version == state.version + 1

    def test_start_spin_invalid_in_round_won(self):
        state = new_game(word="ДА", players=["Анна"])
        from engine.actions import guess_letter
        state = apply(state, guess_letter("д"))
        state = apply(state, guess_letter("а"))
        assert state.phase == "round_won"

        with pytest.raises(InvalidAction):
            apply(state, start_spin())
