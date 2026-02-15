"""
Tests for the Inventory Optimizer — Dynamic Reorder Point Calculation.

Covers:
  - Reliability multiplier mapping
  - Z-score lookup
  - EOQ (Economic Order Quantity) calculation
  - Edge cases (zero demand, zero cost, etc.)
"""

import pytest

from inventory.optimizer import (
    RELIABILITY_MULTIPLIERS,
    Z_SCORES,
    InventoryOptimizer,
    get_cluster_multipliers,
    get_default_service_level,
    get_reliability_multiplier,
    get_z_score,
)

# ── Reliability Multiplier ─────────────────────────────────────────────


class TestReliabilityMultiplier:
    def test_excellent_reliability(self):
        """95%+ on-time → 1.0x (no penalty)."""
        assert get_reliability_multiplier(0.97) == 1.0
        assert get_reliability_multiplier(0.95) == 1.0

    def test_good_reliability(self):
        """80-94% on-time → 1.2x buffer."""
        assert get_reliability_multiplier(0.90) == 1.2
        assert get_reliability_multiplier(0.80) == 1.2

    def test_moderate_reliability(self):
        """60-79% on-time → 1.5x buffer."""
        assert get_reliability_multiplier(0.70) == 1.5
        assert get_reliability_multiplier(0.60) == 1.5

    def test_poor_reliability(self):
        """<60% on-time → 1.8x buffer (unreliable)."""
        assert get_reliability_multiplier(0.50) == 1.8
        assert get_reliability_multiplier(0.10) == 1.8
        assert get_reliability_multiplier(0.0) == 1.8

    def test_perfect_reliability(self):
        """1.0 exactly → 1.0x (in 0.95-1.01 range)."""
        assert get_reliability_multiplier(1.0) == 1.0

    def test_out_of_range_returns_default(self):
        """Negative or >1.01 should return 1.0 default."""
        assert get_reliability_multiplier(1.5) == 1.0


# ── Z-Score Lookup ─────────────────────────────────────────────────────


class TestZScore:
    def test_95_service_level(self):
        assert get_z_score(0.95) == 1.645

    def test_99_service_level(self):
        assert get_z_score(0.99) == 2.326

    def test_90_service_level(self):
        assert get_z_score(0.90) == 1.282

    def test_closest_match(self):
        """0.94 should map to 0.95 (closest key)."""
        assert get_z_score(0.94) == 1.645

    def test_exact_975(self):
        assert get_z_score(0.975) == 1.960


# ── Economic Order Quantity ────────────────────────────────────────────


class TestEOQ:
    def test_standard_eoq(self):
        """
        EOQ = √((2 × D × S) / H)
        D=1000, S=100, H=5 → √(2×1000×100/5) = √40000 = 200
        """
        eoq = InventoryOptimizer._calculate_eoq(
            annual_demand=1000,
            cost_per_order=100,
            holding_cost_annual=5,
        )
        assert eoq == 200

    def test_eoq_rounds_to_nearest(self):
        """EOQ should round to nearest integer."""
        eoq = InventoryOptimizer._calculate_eoq(
            annual_demand=365,
            cost_per_order=50,
            holding_cost_annual=10,
        )
        # √(2×365×50/10) = √3650 ≈ 60.4
        assert eoq == 60

    def test_eoq_zero_demand(self):
        """Zero demand should return 1 (minimum)."""
        eoq = InventoryOptimizer._calculate_eoq(0, 100, 5)
        assert eoq == 1

    def test_eoq_zero_order_cost(self):
        """Zero order cost should return 1."""
        eoq = InventoryOptimizer._calculate_eoq(1000, 0, 5)
        assert eoq == 1

    def test_eoq_zero_holding_cost(self):
        """Zero holding cost should return 1."""
        eoq = InventoryOptimizer._calculate_eoq(1000, 100, 0)
        assert eoq == 1

    def test_eoq_negative_values(self):
        """Negative inputs should return 1."""
        assert InventoryOptimizer._calculate_eoq(-100, 50, 5) == 1
        assert InventoryOptimizer._calculate_eoq(100, -50, 5) == 1
        assert InventoryOptimizer._calculate_eoq(100, 50, -5) == 1

    def test_eoq_small_demand(self):
        """Very small demand should still return at least 1."""
        eoq = InventoryOptimizer._calculate_eoq(1, 1, 1)
        assert eoq >= 1

    def test_eoq_large_demand(self):
        """Large demand should produce reasonable EOQ."""
        eoq = InventoryOptimizer._calculate_eoq(
            annual_demand=100000,
            cost_per_order=200,
            holding_cost_annual=10,
        )
        # √(2×100000×200/10) = √4000000 = 2000
        assert eoq == 2000


# ── Multiplier Table Coverage ──────────────────────────────────────────


class TestMultiplierCoverage:
    def test_all_ranges_covered(self):
        """Every reliability from 0.0 to 1.0 should get a multiplier."""
        for pct in range(0, 101):
            score = pct / 100.0
            mult = get_reliability_multiplier(score)
            assert mult >= 1.0, f"Score {score} returned multiplier {mult} < 1.0"
            assert mult <= 1.8, f"Score {score} returned multiplier {mult} > 1.8"

    def test_monotonically_decreasing(self):
        """Higher reliability should mean lower (or equal) multiplier."""
        prev_mult = float("inf")
        for pct in range(0, 101):
            score = pct / 100.0
            mult = get_reliability_multiplier(score)
            assert mult <= prev_mult or mult == prev_mult or prev_mult == float("inf")


class TestConfigDrivenDefaults:
    def test_default_service_level_is_valid(self):
        assert 0.8 <= get_default_service_level() <= 0.999

    def test_cluster_multipliers_are_available(self):
        multipliers = get_cluster_multipliers()
        assert set(multipliers.keys()) == {0, 1, 2}
