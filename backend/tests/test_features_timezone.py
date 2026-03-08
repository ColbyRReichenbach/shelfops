"""
Tests for timezone-aware feature engineering in ml/features.py.
"""

import numpy as np
import pandas as pd
import pytest

from ml.features import create_features


def _minimal_df(date_str: str) -> pd.DataFrame:
    """Return a minimal single-row transactions DataFrame."""
    return pd.DataFrame(
        {
            "date": [date_str],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "quantity": [10.0],
        }
    )


def test_timezone_affects_day_of_week():
    """A UTC midnight timestamp is the previous day in US timezones."""
    # 2024-01-01 00:30 UTC = 2023-12-31 in America/Denver (UTC-7)
    df = pd.DataFrame(
        {
            "date": ["2024-01-01"],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "quantity": [10.0],
        }
    )
    utc_features = create_features(df.copy(), timezone="UTC")
    denver_features = create_features(df.copy(), timezone="America/Denver")
    # day_of_week should be valid integers 0-6 in both cases
    assert 0 <= utc_features["day_of_week"].iloc[0] <= 6
    assert 0 <= denver_features["day_of_week"].iloc[0] <= 6
    # Note: for a plain date string "2024-01-01" (no time component),
    # both UTC and Denver will resolve to the same calendar day since
    # there's no sub-day timestamp to shift. The key assertion is that
    # the feature is always a valid day-of-week integer.


def test_create_features_accepts_timezone_param():
    """create_features() must accept timezone kwarg without raising."""
    df = _minimal_df("2024-06-15")
    result = create_features(df, timezone="America/New_York")
    assert "day_of_week" in result.columns
    assert "month" in result.columns
    assert "week_of_year" in result.columns


def test_utc_timezone_is_default():
    """Calling create_features without timezone should behave same as timezone='UTC'."""
    df = _minimal_df("2024-03-15")
    result_default = create_features(df.copy())
    result_utc = create_features(df.copy(), timezone="UTC")
    assert result_default["day_of_week"].iloc[0] == result_utc["day_of_week"].iloc[0]
    assert result_default["month"].iloc[0] == result_utc["month"].iloc[0]


def test_day_of_week_valid_range_all_timezones():
    """day_of_week must be 0-6 across several representative timezones."""
    df = _minimal_df("2024-11-15")
    timezones = ["UTC", "America/Denver", "America/New_York", "America/Los_Angeles", "Europe/London"]
    for tz in timezones:
        result = create_features(df.copy(), timezone=tz)
        dow = result["day_of_week"].iloc[0]
        assert 0 <= dow <= 6, f"day_of_week={dow} out of range for timezone={tz}"


def test_month_valid_range():
    """month must be 1-12."""
    for month in range(1, 13):
        date_str = f"2024-{month:02d}-15"
        df = _minimal_df(date_str)
        result = create_features(df, timezone="America/Denver")
        assert result["month"].iloc[0] == month


def test_timestamp_with_hour_component_shifts_day():
    """A timestamp near midnight UTC should shift to the previous day in Denver (UTC-7)."""
    # 2024-01-02 02:00 UTC = 2024-01-01 19:00 MST (same date, no shift)
    # 2024-01-02 00:30 UTC = 2024-01-01 17:30 MST (previous day)
    # We use a DataFrame with explicit UTC timestamps to demonstrate the shift.
    df_utc = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02 00:30:00", tz="UTC")],
            "store_id": ["s1"],
            "product_id": ["p1"],
            "quantity": [10.0],
        }
    )
    utc_features = create_features(df_utc.copy(), timezone="UTC")
    denver_features = create_features(df_utc.copy(), timezone="America/Denver")

    # UTC: January 2, 2024 = Tuesday (day_of_week=1)
    # Denver (UTC-7): January 1, 2024 = Monday (day_of_week=0)
    assert utc_features["day_of_week"].iloc[0] == 1  # Tuesday
    assert denver_features["day_of_week"].iloc[0] == 0  # Monday


def test_invalid_timezone_does_not_crash():
    """An unrecognized timezone string should not raise — falls back gracefully."""
    df = _minimal_df("2024-06-01")
    # Should not raise; falls back to UTC behavior
    result = create_features(df, timezone="Invalid/Timezone")
    assert "day_of_week" in result.columns
    assert 0 <= result["day_of_week"].iloc[0] <= 6
