"""Business-oriented metrics used for model promotion gates."""

from __future__ import annotations

import pandas as pd


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _margin_series(unit_price: pd.Series, unit_cost: pd.Series, default_margin_pct: float) -> pd.Series:
    computed = (unit_price - unit_cost) / unit_price
    computed = computed.where(unit_price > 0)
    return computed.fillna(default_margin_pct).clip(lower=0.0, upper=0.95)


def calculate_overstock_dollars(df: pd.DataFrame) -> tuple[float, str]:
    """
    Calculate overstock dollars at SKU-store-date grain.

    Required columns:
      - predicted_qty
      - actual_qty
    Optional pricing columns:
      - unit_cost (preferred)
      - category
      - category_median_cost (fallback)

    Returns:
      (overstock_dollars, confidence)
      confidence: "measured" when unit_cost exists, "estimated" when category median fallback is used.
    """
    required = {"predicted_qty", "actual_qty"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for overstock calculation: {sorted(missing)}")

    work = df.copy()
    over_units = (
        pd.to_numeric(work["predicted_qty"], errors="coerce") - pd.to_numeric(work["actual_qty"], errors="coerce")
    ).clip(lower=0)

    if "unit_cost" in work.columns and work["unit_cost"].notna().any():
        unit_cost = pd.to_numeric(work["unit_cost"], errors="coerce")
        confidence = "measured"
    elif {"category", "category_median_cost"}.issubset(work.columns):
        unit_cost = pd.to_numeric(work["category_median_cost"], errors="coerce")
        confidence = "estimated"
    else:
        unit_cost = pd.Series([0.0] * len(work))
        confidence = "estimated"

    dollars = (over_units.fillna(0.0) * unit_cost.fillna(0.0)).sum()
    return float(dollars), confidence


def calculate_business_impact_metrics(
    df: pd.DataFrame,
    *,
    default_margin_pct: float = 0.30,
    annual_holding_rate: float = 0.25,
) -> dict[str, float | str | None]:
    """
    Calculate holdout-time business impact proxies from actual vs predicted demand.

    Metrics:
      - lost_sales_qty: under-forecast units
      - opportunity_cost_stockout: lost_sales_qty × unit_price × margin
      - opportunity_cost_overstock: over-forecast units × daily holding cost
      - overstock_dollars: over-forecast units × unit_cost

    Confidence policy:
      - "measured": direct unit_price / unit_cost / holding-cost data exists
      - "estimated": fallback basis exists (category median cost or unit-cost-derived)
      - "unavailable": not enough pricing basis to compute the metric responsibly
    """
    required = {"predicted_qty", "actual_qty"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns for business metrics: {sorted(missing)}")

    work = df.copy()
    predicted = _numeric_series(work, "predicted_qty").fillna(0.0)
    actual = _numeric_series(work, "actual_qty").fillna(0.0)
    lost_sales = (actual - predicted).clip(lower=0.0)
    over_units = (predicted - actual).clip(lower=0.0)

    metrics: dict[str, float | str | None] = {
        "lost_sales_qty": float(lost_sales.sum()),
        "opportunity_cost_stockout": None,
        "opportunity_cost_stockout_confidence": "unavailable",
        "opportunity_cost_overstock": None,
        "opportunity_cost_overstock_confidence": "unavailable",
    }

    unit_cost = _numeric_series(work, "unit_cost", default=float("nan"))
    fallback_cost = _numeric_series(work, "category_median_cost", default=float("nan"))
    effective_cost = unit_cost.copy()
    if effective_cost.isna().all() and "category_median_cost" in work.columns:
        effective_cost = fallback_cost
    else:
        effective_cost = effective_cost.fillna(fallback_cost)

    unit_price = _numeric_series(work, "unit_price", default=float("nan"))
    inferred_price = effective_cost / max(1.0 - default_margin_pct, 1e-6)
    effective_price = unit_price.copy()
    if effective_price.isna().all() and effective_cost.notna().any():
        effective_price = inferred_price
        stockout_confidence = "estimated"
    elif effective_price.notna().any():
        effective_price = effective_price.fillna(inferred_price)
        stockout_confidence = "measured"
    else:
        effective_price = pd.Series([float("nan")] * len(work), index=work.index, dtype="float64")
        stockout_confidence = "unavailable"

    if stockout_confidence != "unavailable":
        margin_pct = _margin_series(effective_price, effective_cost.fillna(0.0), default_margin_pct)
        stockout_cost = (lost_sales * effective_price.fillna(0.0) * margin_pct).sum()
        metrics["opportunity_cost_stockout"] = float(stockout_cost)
        metrics["opportunity_cost_stockout_confidence"] = stockout_confidence

    holding_cost_per_day = _numeric_series(work, "holding_cost_per_unit_per_day", default=float("nan"))
    if holding_cost_per_day.notna().any():
        effective_holding_cost = holding_cost_per_day
        overstock_confidence = "measured"
    elif effective_cost.notna().any():
        effective_holding_cost = effective_cost.fillna(0.0) * annual_holding_rate / 365.0
        overstock_confidence = "estimated"
    else:
        effective_holding_cost = pd.Series([float("nan")] * len(work), index=work.index, dtype="float64")
        overstock_confidence = "unavailable"

    if overstock_confidence != "unavailable":
        overstock_cost = (over_units * effective_holding_cost.fillna(0.0)).sum()
        metrics["opportunity_cost_overstock"] = float(overstock_cost)
        metrics["opportunity_cost_overstock_confidence"] = overstock_confidence

    return metrics
