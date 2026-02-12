"""
Tests for the NRF 4-5-4 Retail Calendar + Holiday Detection.

Covers:
  - Fixed-date holidays (Christmas, July 4th, etc.)
  - Floating holidays (Thanksgiving, Memorial Day, Easter, etc.)
  - 4-5-4 fiscal year start calculation
  - Fiscal period mapping (year, quarter, month, week)
  - Peak shopping week detection
  - Seasonal demand weights
"""

from datetime import date

import pytest

from retail.calendar import RetailCalendar, _compute_easter, get_us_holidays

# ── Fixed-Date Holidays ────────────────────────────────────────────────


class TestFixedHolidays:
    def test_christmas(self):
        assert RetailCalendar.is_holiday(date(2026, 12, 25))
        assert RetailCalendar.get_holiday_name(date(2026, 12, 25)) == "Christmas Day"

    def test_new_years(self):
        assert RetailCalendar.is_holiday(date(2026, 1, 1))
        assert RetailCalendar.get_holiday_name(date(2026, 1, 1)) == "New Year's Day"

    def test_independence_day(self):
        assert RetailCalendar.is_holiday(date(2026, 7, 4))

    def test_valentines_day(self):
        assert RetailCalendar.is_holiday(date(2026, 2, 14))
        assert RetailCalendar.get_holiday_name(date(2026, 2, 14)) == "Valentine's Day"

    def test_halloween(self):
        assert RetailCalendar.is_holiday(date(2026, 10, 31))

    def test_regular_day_is_not_holiday(self):
        assert not RetailCalendar.is_holiday(date(2026, 3, 15))
        assert RetailCalendar.get_holiday_name(date(2026, 3, 15)) is None


# ── Floating Holidays ──────────────────────────────────────────────────


class TestFloatingHolidays:
    def test_thanksgiving_2026(self):
        # 4th Thursday of November 2026 = Nov 26
        assert RetailCalendar.is_holiday(date(2026, 11, 26))
        assert RetailCalendar.get_holiday_name(date(2026, 11, 26)) == "Thanksgiving"

    def test_black_friday_2026(self):
        # Day after Thanksgiving = Nov 27
        assert RetailCalendar.is_holiday(date(2026, 11, 27))
        assert RetailCalendar.get_holiday_name(date(2026, 11, 27)) == "Black Friday"

    def test_cyber_monday_2026(self):
        # 3 days after Thanksgiving = Nov 29
        assert RetailCalendar.is_holiday(date(2026, 11, 29))
        assert RetailCalendar.get_holiday_name(date(2026, 11, 29)) == "Cyber Monday"

    def test_memorial_day_2026(self):
        # Last Monday of May 2026 = May 25
        assert RetailCalendar.is_holiday(date(2026, 5, 25))
        assert RetailCalendar.get_holiday_name(date(2026, 5, 25)) == "Memorial Day"

    def test_labor_day_2026(self):
        # 1st Monday of September 2026 = Sep 7
        assert RetailCalendar.is_holiday(date(2026, 9, 7))
        assert RetailCalendar.get_holiday_name(date(2026, 9, 7)) == "Labor Day"

    def test_mlk_day_2026(self):
        # 3rd Monday of January 2026 = Jan 19
        assert RetailCalendar.is_holiday(date(2026, 1, 19))
        assert RetailCalendar.get_holiday_name(date(2026, 1, 19)) == "MLK Day"

    def test_mothers_day_2026(self):
        # 2nd Sunday of May 2026 = May 10
        assert RetailCalendar.is_holiday(date(2026, 5, 10))
        assert RetailCalendar.get_holiday_name(date(2026, 5, 10)) == "Mother's Day"

    def test_fathers_day_2026(self):
        # 3rd Sunday of June 2026 = Jun 21
        assert RetailCalendar.is_holiday(date(2026, 6, 21))
        assert RetailCalendar.get_holiday_name(date(2026, 6, 21)) == "Father's Day"


# ── Easter (Anonymous Gregorian Algorithm) ─────────────────────────────


class TestEaster:
    """Verify Easter dates against known values."""

    def test_easter_2024(self):
        assert _compute_easter(2024) == date(2024, 3, 31)

    def test_easter_2025(self):
        assert _compute_easter(2025) == date(2025, 4, 20)

    def test_easter_2026(self):
        assert _compute_easter(2026) == date(2026, 4, 5)

    def test_easter_2027(self):
        assert _compute_easter(2027) == date(2027, 3, 28)

    def test_easter_is_holiday(self):
        easter_2026 = _compute_easter(2026)
        assert RetailCalendar.is_holiday(easter_2026)
        assert RetailCalendar.get_holiday_name(easter_2026) == "Easter Sunday"


# ── Holiday Count ──────────────────────────────────────────────────────


class TestHolidayCount:
    def test_at_least_16_holidays_per_year(self):
        """We define 16+ holidays (fixed + floating + retail)."""
        holidays = get_us_holidays(2026)
        assert len(holidays) >= 16

    def test_holidays_cached(self):
        """LRU cache means same object returned."""
        h1 = get_us_holidays(2026)
        h2 = get_us_holidays(2026)
        assert h1 is h2


# ── Days to Next Holiday ──────────────────────────────────────────────


class TestDaysToNextHoliday:
    def test_on_holiday_returns_zero(self):
        assert RetailCalendar.days_to_next_holiday(date(2026, 12, 25)) == 0

    def test_day_before_holiday(self):
        assert RetailCalendar.days_to_next_holiday(date(2026, 12, 24)) == 1

    def test_near_year_end_looks_into_next_year(self):
        # Dec 31 is New Year's Eve (holiday), so 0
        assert RetailCalendar.days_to_next_holiday(date(2026, 12, 31)) == 0
        # Dec 26 — next holiday is Dec 31 (New Year's Eve)
        assert RetailCalendar.days_to_next_holiday(date(2026, 12, 26)) == 5


# ── 4-5-4 Fiscal Calendar ─────────────────────────────────────────────


class TestFiscalYearStart:
    def test_fiscal_year_start_is_sunday(self):
        """Fiscal year always starts on a Sunday."""
        for year in range(2020, 2030):
            start = RetailCalendar.fiscal_year_start(year)
            assert start.weekday() == 6, f"FY{year} start {start} is not Sunday"

    def test_fiscal_year_start_near_jan_31(self):
        """Fiscal year start should be within 3 days of Jan 31."""
        for year in range(2020, 2030):
            start = RetailCalendar.fiscal_year_start(year)
            jan31 = date(year, 1, 31)
            delta = abs((start - jan31).days)
            assert delta <= 3, f"FY{year} start {start} is {delta} days from Jan 31"


class TestFiscalPeriod:
    def test_fiscal_quarter_range(self):
        period = RetailCalendar.get_fiscal_period(date(2026, 6, 15))
        assert 1 <= period.fiscal_quarter <= 4

    def test_fiscal_month_range(self):
        period = RetailCalendar.get_fiscal_period(date(2026, 6, 15))
        assert 1 <= period.fiscal_month <= 12

    def test_fiscal_week_range(self):
        period = RetailCalendar.get_fiscal_period(date(2026, 6, 15))
        assert 1 <= period.fiscal_week <= 53

    def test_fiscal_year_assignment(self):
        """Dates near fiscal year boundary should map correctly."""
        # Well into the fiscal year
        period = RetailCalendar.get_fiscal_period(date(2026, 6, 1))
        assert period.fiscal_year == 2026

    def test_454_pattern_weeks(self):
        """Quarter 1 should have 4+5+4 = 13 weeks."""
        fy_start = RetailCalendar.fiscal_year_start(2026)
        # End of fiscal month 1 (4 weeks)
        from datetime import timedelta

        end_m1 = fy_start + timedelta(weeks=4) - timedelta(days=1)
        period = RetailCalendar.get_fiscal_period(end_m1)
        assert period.fiscal_month == 1

        # Start of fiscal month 2 (week 5)
        start_m2 = fy_start + timedelta(weeks=4)
        period = RetailCalendar.get_fiscal_period(start_m2)
        assert period.fiscal_month == 2


# ── Peak Shopping Weeks ────────────────────────────────────────────────


class TestPeakShopping:
    def test_back_to_school_is_peak(self):
        assert RetailCalendar.is_peak_shopping_week(date(2026, 8, 15))

    def test_early_september_is_peak(self):
        assert RetailCalendar.is_peak_shopping_week(date(2026, 9, 5))

    def test_mid_march_is_not_peak(self):
        assert not RetailCalendar.is_peak_shopping_week(date(2026, 3, 15))


# ── Seasonal Weights ──────────────────────────────────────────────────


class TestSeasonalWeights:
    def test_holiday_season_bakery(self):
        weight = RetailCalendar.get_seasonal_weight(date(2026, 12, 15), "Bakery")
        assert weight == 1.5

    def test_holiday_season_hardware(self):
        weight = RetailCalendar.get_seasonal_weight(date(2026, 12, 15), "Hardware")
        assert weight == 0.4

    def test_normal_day_returns_1(self):
        weight = RetailCalendar.get_seasonal_weight(date(2026, 3, 15), "general")
        assert weight == 1.0

    def test_summer_hardware(self):
        weight = RetailCalendar.get_seasonal_weight(date(2026, 7, 15), "Hardware")
        assert weight == 1.3
