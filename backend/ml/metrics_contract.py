"""
Canonical forecast metric definitions used across training, backtest, and benchmarking.

Target semantics policy (hardening baseline):
  - Quantity represents net demand magnitude at the evaluation grain.
  - Sales contribute positive quantity, returns contribute negative quantity.
  - Benchmark/backtest/train comparisons must use the same signed-demand policy.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.business_metrics import calculate_business_impact_metrics, calculate_overstock_dollars
from ml.metrics import bias_pct as compute_bias_pct
from ml.metrics import mase as compute_mase
from ml.metrics import wape as compute_wape


def _to_series(values: Any) -> pd.Series:
    series = pd.Series(values).reset_index(drop=True)
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def mae(y_true: Any, y_pred: Any) -> float:
    actual = _to_series(y_true)
    pred = _to_series(y_pred)
    return float(np.abs(pred - actual).mean())


def mape_nonzero(y_true: Any, y_pred: Any) -> float:
    actual = _to_series(y_true)
    pred = _to_series(y_pred)
    mask = actual > 0
    if int(mask.sum()) == 0:
        return 0.0
    return float((np.abs(pred[mask] - actual[mask]) / actual[mask]).mean())


def stockout_miss_rate(y_true: Any, y_pred: Any) -> float:
    """
    Missed-demand proxy:
      actual demand > 0 but model predicted <= 0.
    """
    actual = _to_series(y_true)
    pred = _to_series(y_pred)
    return float(((actual > 0) & (pred <= 0)).mean())


def overstock_rate(y_true: Any, y_pred: Any) -> float:
    actual = _to_series(y_true)
    pred = _to_series(y_pred)
    return float((pred > actual).mean())


def coverage_rate(y_true: Any, lower_bound: Any, upper_bound: Any) -> float:
    actual = _to_series(y_true)
    lower = _to_series(lower_bound)
    upper = _to_series(upper_bound)
    return float(((actual >= lower) & (actual <= upper)).mean())


def overstock_dollars(
    y_true: Any,
    y_pred: Any,
    unit_cost: Any | None = None,
    category: Any | None = None,
    category_median_cost: Any | None = None,
) -> tuple[float | None, str]:
    """
    Returns (value, confidence).
    If neither measured nor fallback costs are present, returns (None, "unavailable").
    """
    frame = pd.DataFrame(
        {
            "actual_qty": _to_series(y_true),
            "predicted_qty": _to_series(y_pred),
        }
    )
    if unit_cost is not None:
        frame["unit_cost"] = _to_series(unit_cost)
    if category is not None:
        frame["category"] = pd.Series(category).astype("string")
    if category_median_cost is not None:
        frame["category_median_cost"] = _to_series(category_median_cost)

    has_unit_cost = "unit_cost" in frame.columns and frame["unit_cost"].notna().any()
    has_fallback = {"category", "category_median_cost"}.issubset(frame.columns) and frame[
        "category_median_cost"
    ].notna().any()
    if not has_unit_cost and not has_fallback:
        return None, "unavailable"

    value, confidence = calculate_overstock_dollars(frame)
    return float(value), confidence


def compute_forecast_metrics(
    y_true: Any,
    y_pred: Any,
    *,
    unit_cost: Any | None = None,
    unit_price: Any | None = None,
    holding_cost_per_unit_per_day: Any | None = None,
    category: Any | None = None,
    category_median_cost: Any | None = None,
) -> dict[str, float | None | str]:
    frame = pd.DataFrame(
        {
            "actual_qty": _to_series(y_true),
            "predicted_qty": _to_series(y_pred),
        }
    )
    if unit_cost is not None:
        frame["unit_cost"] = _to_series(unit_cost)
    if unit_price is not None:
        frame["unit_price"] = _to_series(unit_price)
    if holding_cost_per_unit_per_day is not None:
        frame["holding_cost_per_unit_per_day"] = _to_series(holding_cost_per_unit_per_day)
    if category is not None:
        frame["category"] = pd.Series(category).astype("string")
    if category_median_cost is not None:
        frame["category_median_cost"] = _to_series(category_median_cost)

    over_dollars, over_conf = overstock_dollars(
        frame["actual_qty"],
        frame["predicted_qty"],
        unit_cost=frame["unit_cost"] if "unit_cost" in frame.columns else None,
        category=frame["category"] if "category" in frame.columns else None,
        category_median_cost=frame["category_median_cost"] if "category_median_cost" in frame.columns else None,
    )
    business_metrics = calculate_business_impact_metrics(frame)
    return {
        "mae": mae(y_true, y_pred),
        "mape_nonzero": mape_nonzero(y_true, y_pred),
        "wape": compute_wape(y_true, y_pred),
        "mase": compute_mase(_to_series(y_true).to_numpy(), _to_series(y_pred).to_numpy(), seasonality=7),
        "bias_pct": compute_bias_pct(y_true, y_pred),
        "stockout_miss_rate": stockout_miss_rate(y_true, y_pred),
        "overstock_rate": overstock_rate(y_true, y_pred),
        "overstock_dollars": over_dollars,
        "overstock_dollars_confidence": over_conf,
        "lost_sales_qty": business_metrics["lost_sales_qty"],
        "opportunity_cost_stockout": business_metrics["opportunity_cost_stockout"],
        "opportunity_cost_stockout_confidence": business_metrics["opportunity_cost_stockout_confidence"],
        "opportunity_cost_overstock": business_metrics["opportunity_cost_overstock"],
        "opportunity_cost_overstock_confidence": business_metrics["opportunity_cost_overstock_confidence"],
    }
