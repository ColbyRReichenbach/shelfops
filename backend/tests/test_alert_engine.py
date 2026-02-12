"""
Tests for the Alert Engine — Severity Classification.

Covers:
  - Stockout severity classification
  - Anomaly severity classification
"""

import pytest

from alerts.engine import classify_anomaly_severity, classify_severity

# ── Stockout Severity ──────────────────────────────────────────────────


class TestStockoutSeverity:
    def test_critical_one_day(self):
        assert classify_severity(1) == "critical"

    def test_critical_half_day(self):
        assert classify_severity(0.5) == "critical"

    def test_critical_zero_days(self):
        assert classify_severity(0) == "critical"

    def test_high_two_days(self):
        assert classify_severity(2) == "high"

    def test_high_three_days(self):
        assert classify_severity(3) == "high"

    def test_medium_four_days(self):
        assert classify_severity(4) == "medium"

    def test_medium_five_days(self):
        assert classify_severity(5) == "medium"

    def test_low_six_days(self):
        assert classify_severity(6) == "low"

    def test_low_ten_days(self):
        assert classify_severity(10) == "low"


# ── Anomaly Severity ──────────────────────────────────────────────────


class TestAnomalySeverity:
    def test_critical_high_z(self):
        assert classify_anomaly_severity(4.5) == "critical"

    def test_critical_exact_threshold(self):
        assert classify_anomaly_severity(4.0) == "critical"

    def test_high_z(self):
        assert classify_anomaly_severity(3.5) == "high"

    def test_medium_z(self):
        assert classify_anomaly_severity(2.7) == "medium"

    def test_low_z(self):
        assert classify_anomaly_severity(2.0) == "low"

    def test_negative_z_uses_absolute(self):
        """Negative z-scores should use absolute value."""
        assert classify_anomaly_severity(-4.5) == "critical"
        assert classify_anomaly_severity(-3.0) == "high"

    def test_below_threshold(self):
        """Z-score below 2.0 should still return low."""
        assert classify_anomaly_severity(1.5) == "low"
