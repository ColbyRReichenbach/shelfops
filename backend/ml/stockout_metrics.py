from __future__ import annotations

from typing import Any

import pandas as pd

from ml.metrics_contract import compute_forecast_metrics


def _numeric(values: Any) -> pd.Series:
    return pd.to_numeric(pd.Series(values), errors="coerce").fillna(0.0).reset_index(drop=True)


def _boolean_mask(values: Any) -> pd.Series:
    raw = pd.Series(values).reset_index(drop=True)
    if raw.dtype == object:
        return raw.astype(str).str.lower().isin({"1", "true", "yes", "stockout", "window"})
    return pd.to_numeric(raw, errors="coerce").fillna(0).astype(int) > 0


def stockout_window_bias(y_true: Any, y_pred: Any, stockout_window: Any) -> float:
    actual = _numeric(y_true)
    pred = _numeric(y_pred)
    mask = _boolean_mask(stockout_window)
    if int(mask.sum()) == 0:
        return 0.0
    return float((pred[mask] - actual[mask]).mean())


def underforecast_rate_during_stockouts(y_true: Any, y_pred: Any, stockout_window: Any) -> float:
    actual = _numeric(y_true)
    pred = _numeric(y_pred)
    mask = _boolean_mask(stockout_window)
    if int(mask.sum()) == 0:
        return 0.0
    return float((pred[mask] < actual[mask]).mean())


def evaluate_stockout_windows(
    y_true: Any,
    y_pred: Any,
    stockout_window: Any,
    *,
    estimated_recovered_target: Any | None = None,
) -> dict[str, float | str | None]:
    actual = _numeric(y_true)
    pred = _numeric(y_pred)
    stockout_mask = _boolean_mask(stockout_window)
    non_stockout_mask = ~stockout_mask

    result: dict[str, float | str | None] = {
        "stockout_window_rows": int(stockout_mask.sum()),
        "non_stockout_rows": int(non_stockout_mask.sum()),
        "stockout_window_bias": stockout_window_bias(actual, pred, stockout_mask),
        "underforecast_rate_during_stockouts": underforecast_rate_during_stockouts(actual, pred, stockout_mask),
        "non_stockout_wape": None,
        "non_stockout_mase": None,
        "estimated_recovered_demand_gap": None,
        "estimated_recovered_demand_gap_confidence": "not_available",
    }

    if int(non_stockout_mask.sum()) > 0:
        non_stockout_metrics = compute_forecast_metrics(actual[non_stockout_mask], pred[non_stockout_mask])
        result["non_stockout_wape"] = float(non_stockout_metrics["wape"])
        result["non_stockout_mase"] = float(non_stockout_metrics["mase"])

    if estimated_recovered_target is not None and int(stockout_mask.sum()) > 0:
        recovered = _numeric(estimated_recovered_target)
        gap = pred[stockout_mask] - recovered[stockout_mask]
        result["estimated_recovered_demand_gap"] = float(gap.mean())
        result["estimated_recovered_demand_gap_confidence"] = "estimated"

    return result
