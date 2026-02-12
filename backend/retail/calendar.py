"""
Retail Calendar — US Retail 4-5-4 Fiscal Calendar + Holiday Detection.

Demonstrates deep retail domain knowledge:
  - NRF 4-5-4 fiscal calendar (standard for Target, Walmart, Lowe's)
  - US federal holidays + major retail events
  - Peak shopping week detection (Black Friday, Christmas, etc.)

The 4-5-4 calendar:
  - Fiscal year starts on the Sunday closest to January 31
  - Each quarter has 3 months: 4 weeks, 5 weeks, 4 weeks
  - 52 weeks per year (53 in leap years — extra week in Q4)
  - Used for comparable sales ("comp sales") reporting

Agent: data-engineer
Skill: postgresql
"""

from datetime import date, timedelta
from functools import lru_cache
from typing import NamedTuple


class FiscalPeriod(NamedTuple):
    fiscal_year: int
    fiscal_quarter: int  # 1-4
    fiscal_month: int  # 1-12
    fiscal_week: int  # 1-52 (or 53)


# ── US Federal + Retail Holidays ─────────────────────────────────────────


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Find the nth occurrence of a weekday in a given month.

    weekday: 0=Monday ... 6=Sunday
    n: 1=first, 2=second, -1=last
    """
    if n > 0:
        first = date(year, month, 1)
        # Days until first occurrence of weekday
        offset = (weekday - first.weekday()) % 7
        first_occurrence = first + timedelta(days=offset)
        return first_occurrence + timedelta(weeks=n - 1)
    else:
        # Last occurrence
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        offset = (last_day.weekday() - weekday) % 7
        return last_day - timedelta(days=offset)


@lru_cache(maxsize=32)
def get_us_holidays(year: int) -> dict[date, str]:
    """Return all US federal + major retail holidays for a year.

    Includes both fixed-date and floating holidays.
    """
    holidays = {}

    # Fixed-date holidays
    holidays[date(year, 1, 1)] = "New Year's Day"
    holidays[date(year, 7, 4)] = "Independence Day"
    holidays[date(year, 12, 25)] = "Christmas Day"
    holidays[date(year, 12, 31)] = "New Year's Eve"

    # Floating holidays
    holidays[_nth_weekday_of_month(year, 1, 0, 3)] = "MLK Day"  # 3rd Monday Jan
    holidays[_nth_weekday_of_month(year, 2, 0, 3)] = "Presidents' Day"  # 3rd Monday Feb
    holidays[_nth_weekday_of_month(year, 5, 0, -1)] = "Memorial Day"  # Last Monday May
    holidays[_nth_weekday_of_month(year, 9, 0, 1)] = "Labor Day"  # 1st Monday Sep
    holidays[_nth_weekday_of_month(year, 10, 0, 2)] = "Columbus Day"  # 2nd Monday Oct
    holidays[_nth_weekday_of_month(year, 11, 3, 4)] = "Thanksgiving"  # 4th Thursday Nov

    # Retail-specific derived holidays
    thanksgiving = _nth_weekday_of_month(year, 11, 3, 4)
    holidays[thanksgiving + timedelta(days=1)] = "Black Friday"
    holidays[thanksgiving + timedelta(days=3)] = "Cyber Monday"

    # Super Bowl Sunday (1st Sunday in Feb — approximation)
    holidays[_nth_weekday_of_month(year, 2, 6, 1)] = "Super Bowl Sunday"

    # Easter (complex calculation — approximate for retail purposes)
    easter = _compute_easter(year)
    holidays[easter] = "Easter Sunday"
    holidays[easter - timedelta(days=1)] = "Easter Saturday"

    # Mother's Day (2nd Sunday May) — big retail day
    holidays[_nth_weekday_of_month(year, 5, 6, 2)] = "Mother's Day"

    # Father's Day (3rd Sunday June)
    holidays[_nth_weekday_of_month(year, 6, 6, 3)] = "Father's Day"

    # Valentine's Day
    holidays[date(year, 2, 14)] = "Valentine's Day"

    # Halloween
    holidays[date(year, 10, 31)] = "Halloween"

    return holidays


def _compute_easter(year: int) -> date:
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


# ── Holiday Detection ────────────────────────────────────────────────────


class RetailCalendar:
    """US Retail 4-5-4 fiscal calendar + holidays."""

    @staticmethod
    def is_holiday(dt: date) -> bool:
        """Return True if the given date is a US federal or major retail holiday."""
        holidays = get_us_holidays(dt.year)
        return dt in holidays

    @staticmethod
    def get_holiday_name(dt: date) -> str | None:
        """Return the holiday name, or None if not a holiday."""
        holidays = get_us_holidays(dt.year)
        return holidays.get(dt)

    @staticmethod
    def days_to_next_holiday(dt: date) -> int:
        """Days until the next holiday (for ML feature engineering)."""
        holidays = get_us_holidays(dt.year)
        # Also check next year in case near Dec 31
        holidays.update(get_us_holidays(dt.year + 1))
        future = sorted(d for d in holidays if d >= dt)
        return (future[0] - dt).days if future else 365

    # ── 4-5-4 Fiscal Calendar ────────────────────────────────────────

    @staticmethod
    @lru_cache(maxsize=32)
    def fiscal_year_start(fiscal_year: int) -> date:
        """
        NRF 4-5-4: Fiscal year starts on the Sunday closest to January 31.

        This is the standard used by Target, Walmart, Macy's, etc.
        """
        jan31 = date(fiscal_year, 1, 31)
        # Find Sunday closest to Jan 31
        day_of_week = jan31.weekday()  # 0=Mon, 6=Sun
        if day_of_week == 6:
            return jan31  # Already Sunday
        days_since_sunday = (day_of_week + 1) % 7
        prev_sunday = jan31 - timedelta(days=days_since_sunday)
        next_sunday = prev_sunday + timedelta(days=7)
        # Pick whichever is closer to Jan 31
        if (jan31 - prev_sunday).days <= (next_sunday - jan31).days:
            return prev_sunday
        return next_sunday

    @staticmethod
    def get_fiscal_period(dt: date) -> FiscalPeriod:
        """
        Convert a calendar date to its NRF 4-5-4 fiscal period.

        Returns (fiscal_year, fiscal_quarter, fiscal_month, fiscal_week).
        """
        # Determine which fiscal year this date falls in
        fy_start = RetailCalendar.fiscal_year_start(dt.year)
        if dt < fy_start:
            fy_start = RetailCalendar.fiscal_year_start(dt.year - 1)
            fiscal_year = dt.year - 1
        else:
            next_fy_start = RetailCalendar.fiscal_year_start(dt.year + 1)
            if dt >= next_fy_start:
                fy_start = next_fy_start
                fiscal_year = dt.year + 1
            else:
                fiscal_year = dt.year

        # Calculate week number (1-indexed)
        days_since_start = (dt - fy_start).days
        fiscal_week = days_since_start // 7 + 1

        # 4-5-4 pattern: Month 1=4wk, Month 2=5wk, Month 3=4wk, repeat
        # Cumulative weeks per month: 4, 9, 13, 17, 22, 26, 30, 35, 39, 43, 48, 52
        CUMULATIVE_WEEKS = [0, 4, 9, 13, 17, 22, 26, 30, 35, 39, 43, 48, 52]

        fiscal_month = 12  # Default to last month
        for m in range(1, 13):
            if fiscal_week <= CUMULATIVE_WEEKS[m]:
                fiscal_month = m
                break

        fiscal_quarter = (fiscal_month - 1) // 3 + 1

        return FiscalPeriod(
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            fiscal_month=fiscal_month,
            fiscal_week=min(fiscal_week, 53),
        )

    @staticmethod
    def is_peak_shopping_week(dt: date) -> bool:
        """
        Returns True during peak retail weeks:
          - Thanksgiving week (Black Friday)
          - Christmas week (Dec 18-25)
          - Back-to-school (Aug 1 - Sep 7)
          - Spring break (Easter -7 to Easter +1)
        """
        period = RetailCalendar.get_fiscal_period(dt)

        # Thanksgiving / Black Friday / Cyber Monday (fiscal weeks ~47-48)
        if period.fiscal_week in (47, 48):
            return True

        # Christmas (fiscal weeks ~51-52)
        if period.fiscal_week in (51, 52):
            return True

        # Back-to-school (calendar based: Aug 1 - Sep 7)
        if (dt.month == 8) or (dt.month == 9 and dt.day <= 7):
            return True

        return False

    @staticmethod
    def get_seasonal_weight(dt: date, category: str = "general") -> float:
        """
        Return a seasonal demand multiplier (1.0 = normal).

        Category-aware: Holiday demand for Bakery (1.5x) differs from Hardware (0.4x).
        """
        # Holiday season multipliers (Nov 15 - Dec 31)
        HOLIDAY_WEIGHTS = {
            "Bakery": 1.5,
            "Produce": 1.1,
            "Dairy": 1.2,
            "Meat & Seafood": 1.3,
            "Center Store": 1.1,
            "Health & Beauty": 1.3,
            "Electronics": 1.4,
            "Apparel": 1.3,
            "Hardware": 0.4,
            "general": 1.2,
        }

        if dt.month == 11 and dt.day >= 15 or dt.month == 12:
            return HOLIDAY_WEIGHTS.get(category, 1.2)

        # Summer (Jun-Aug): seasonal items spike
        if dt.month in (6, 7, 8):
            if category in ("Produce", "Bakery"):
                return 1.1
            elif category == "Hardware":
                return 1.3  # Home improvement season

        return 1.0
