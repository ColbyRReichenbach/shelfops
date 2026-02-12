"""
Tests for the Shrinkage Adjuster — Category-Based Inventory Adjustment.

Covers:
  - apply_shrinkage_adjustment calculation
  - Edge cases (zero inventory, zero days, high shrink)
  - Default rate lookup
"""

import pytest

from retail.shrinkage import (
    DEFAULT_OVERALL_RATE,
    DEFAULT_SHRINK_RATES,
    apply_shrinkage_adjustment,
)

# ── Core Adjustment Calculation ────────────────────────────────────────


class TestShrinkageAdjustment:
    def test_basic_adjustment(self):
        """100 units, 30 days, 4.8% annual → ~99.6 → 100 (rounded)."""
        result = apply_shrinkage_adjustment(100, 30, 0.048)
        # 100 × (1 - 0.048 × 30/365) = 100 × 0.99605 = 99.6 → 100
        assert result == 100

    def test_longer_period(self):
        """100 units, 180 days, 4.8% annual → ~97.6 → 98."""
        result = apply_shrinkage_adjustment(100, 180, 0.048)
        # 100 × (1 - 0.048 × 180/365) = 100 × 0.97634 = 97.6 → 98
        assert result == 98

    def test_high_shrink_bakery(self):
        """100 units, 90 days, 8% annual → ~98."""
        result = apply_shrinkage_adjustment(100, 90, 0.08)
        # 100 × (1 - 0.08 × 90/365) = 100 × 0.98027 = 98.03 → 98
        assert result == 98

    def test_full_year_center_store(self):
        """1000 units, 365 days, 1% annual → 990."""
        result = apply_shrinkage_adjustment(1000, 365, 0.01)
        # 1000 × (1 - 0.01) = 990
        assert result == 990


# ── Edge Cases ────────────────────────────────────────────────────────


class TestShrinkageEdgeCases:
    def test_zero_inventory(self):
        """Zero inventory should return 0."""
        assert apply_shrinkage_adjustment(0, 30, 0.048) == 0

    def test_negative_inventory(self):
        """Negative inventory should return 0."""
        assert apply_shrinkage_adjustment(-10, 30, 0.048) == 0

    def test_zero_days(self):
        """Zero days since count → no adjustment."""
        assert apply_shrinkage_adjustment(100, 0, 0.048) == 100

    def test_negative_days(self):
        """Negative days → no adjustment (just return qty)."""
        assert apply_shrinkage_adjustment(100, -5, 0.048) == 100

    def test_zero_shrink_rate(self):
        """Zero shrink rate → no adjustment."""
        assert apply_shrinkage_adjustment(100, 365, 0.0) == 100

    def test_extreme_shrink_rate_capped_at_50_percent(self):
        """Even 100% shrink rate should never reduce below 50%."""
        result = apply_shrinkage_adjustment(100, 365, 1.0)
        # Would be 100 × (1 - 1.0) = 0, but capped at 50%
        assert result == 50

    def test_very_long_period_capped(self):
        """Extremely long period with high shrink → capped at 50%."""
        result = apply_shrinkage_adjustment(100, 3000, 0.50)
        # Without cap: 100 × (1 - 0.50 × 3000/365) = deeply negative
        # Capped at 50% → 50
        assert result == 50

    def test_single_unit(self):
        """Single unit with small shrink → still 1."""
        result = apply_shrinkage_adjustment(1, 30, 0.01)
        assert result == 1


# ── Default Rate Benchmarks ───────────────────────────────────────────


class TestDefaultRates:
    def test_bakery_highest_shrink(self):
        """Bakery should have highest shrink rate (spoilage)."""
        assert DEFAULT_SHRINK_RATES["Bakery"] == 0.08
        assert DEFAULT_SHRINK_RATES["Bakery"] == max(DEFAULT_SHRINK_RATES.values())

    def test_center_store_lowest_shrink(self):
        """Center Store should have lowest shrink rate (shelf-stable)."""
        assert DEFAULT_SHRINK_RATES["Center Store"] == 0.01
        assert DEFAULT_SHRINK_RATES["Center Store"] == min(DEFAULT_SHRINK_RATES.values())

    def test_overall_rate_reasonable(self):
        """Overall default rate should be between 1-3%."""
        assert 0.01 <= DEFAULT_OVERALL_RATE <= 0.03

    def test_all_rates_under_10_percent(self):
        """No category should have >10% annual shrink."""
        for cat, rate in DEFAULT_SHRINK_RATES.items():
            assert rate <= 0.10, f"{cat} shrink rate {rate} exceeds 10%"

    def test_all_rates_positive(self):
        """All shrink rates should be positive."""
        for cat, rate in DEFAULT_SHRINK_RATES.items():
            assert rate > 0, f"{cat} shrink rate is not positive"
