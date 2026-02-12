"""
Tests for the Supply Chain Sourcing Engine.

Covers:
  - Haversine distance calculation
  - Lead time estimation helpers
"""

import pytest

from supply_chain.sourcing import haversine_miles

# ── Haversine Distance ─────────────────────────────────────────────────


class TestHaversineDistance:
    def test_same_point_is_zero(self):
        """Same coordinates should return 0."""
        dist = haversine_miles(42.0, -89.0, 42.0, -89.0)
        assert dist == 0.0

    def test_known_distance_chicago_milwaukee(self):
        """Chicago (41.88, -87.63) to Milwaukee (43.04, -87.91) ≈ 82 miles."""
        dist = haversine_miles(41.88, -87.63, 43.04, -87.91)
        assert 75 < dist < 95

    def test_known_distance_minneapolis_chicago(self):
        """Minneapolis (44.98, -93.27) to Chicago (41.88, -87.63) ≈ 355 miles."""
        dist = haversine_miles(44.98, -93.27, 41.88, -87.63)
        assert 340 < dist < 370

    def test_symmetry(self):
        """Distance A→B should equal distance B→A."""
        d1 = haversine_miles(42.0, -89.0, 44.0, -93.0)
        d2 = haversine_miles(44.0, -93.0, 42.0, -89.0)
        assert abs(d1 - d2) < 0.01

    def test_short_distance(self):
        """Points 0.01 degrees apart ≈ 0.5-1 mile."""
        dist = haversine_miles(42.00, -89.00, 42.01, -89.00)
        assert 0.3 < dist < 1.5

    def test_cross_country(self):
        """NYC to LA ≈ 2,450 miles."""
        dist = haversine_miles(40.71, -74.01, 34.05, -118.24)
        assert 2400 < dist < 2500
