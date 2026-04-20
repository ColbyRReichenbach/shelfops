from __future__ import annotations

import math

import numpy as np

from ml.metrics_contract import coverage_rate


def conformal_residual_quantile(y_true: np.ndarray, y_pred: np.ndarray, *, alpha: float = 0.1) -> float:
    actual = np.asarray(y_true, dtype=float)
    pred = np.asarray(y_pred, dtype=float)
    residuals = np.abs(actual - pred)
    if residuals.size == 0:
        return 0.0
    q = math.ceil((residuals.size + 1) * (1 - alpha)) / residuals.size
    q = min(max(q, 0.0), 1.0)
    return float(np.quantile(residuals, q))


def conformal_interval(y_pred: np.ndarray, residual_quantile: float) -> tuple[np.ndarray, np.ndarray]:
    pred = np.asarray(y_pred, dtype=float)
    lower = np.maximum(pred - residual_quantile, 0.0)
    upper = pred + residual_quantile
    return lower, upper


def calibration_summary(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict[str, float]:
    actual = np.asarray(y_true, dtype=float)
    low = np.asarray(lower, dtype=float)
    up = np.asarray(upper, dtype=float)
    return {
        "coverage": float(coverage_rate(actual, low, up)),
        "mean_interval_width": float(np.mean(up - low)) if len(up) else 0.0,
    }
