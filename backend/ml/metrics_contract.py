"""Canonical forecast metric definitions used across training, backtest, and benchmarking."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.business_metrics import calculate_overstock_dollars


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
    category: Any | None = None,
    category_median_cost: Any | None = None,
) -> dict[str, float | None | str]:
    over_dollars, over_conf = overstock_dollars(
        y_true,
        y_pred,
        unit_cost=unit_cost,
        category=category,
        category_median_cost=category_median_cost,
    )
    return {
        "mae": mae(y_true, y_pred),
        "mape_nonzero": mape_nonzero(y_true, y_pred),
        "stockout_miss_rate": stockout_miss_rate(y_true, y_pred),
        "overstock_rate": overstock_rate(y_true, y_pred),
        "overstock_dollars": over_dollars,
        "overstock_dollars_confidence": over_conf,
    }
