"""Business-oriented metrics used for model promotion gates."""

from __future__ import annotations

import pandas as pd


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
