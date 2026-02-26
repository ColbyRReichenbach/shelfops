"""
ShelfOps ML Metrics — WAPE and MASE replace MAPE for demand forecasting.

MAPE: undefined when actual=0 (common in retail), undefined behaviour
WAPE: sum(|actual-pred|) / sum(|actual|) — handles zeros, interpretable
MASE: MAE / MAE_naive — scale-free, works across SKUs with different volumes
"""

import numpy as np
import pandas as pd


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """
    Weighted Absolute Percentage Error.

    Handles zero actuals gracefully — returns 0.0 when sum(|actual|) == 0.

    Formula: sum(|actual - predicted|) / sum(|actual|)

    Args:
        actual: Ground-truth demand values.
        predicted: Model-predicted demand values.

    Returns:
        WAPE as a float in [0, inf). Lower is better; 0 is perfect.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denominator = np.sum(np.abs(actual))
    if denominator == 0:
        return 0.0
    return float(np.sum(np.abs(actual - predicted)) / denominator)


def mase(actual: np.ndarray, predicted: np.ndarray, seasonality: int = 1) -> float:
    """
    Mean Absolute Scaled Error.

    Scale-free metric that compares the model's MAE against the MAE of a
    naive seasonal forecast (lag-seasonality). MASE < 1.0 means the model
    beats the naive baseline.

    Formula: MAE_model / MAE_naive
      where MAE_naive = mean(|actual[t] - actual[t - seasonality]|)

    Args:
        actual: Ground-truth demand values (sorted chronologically).
        predicted: Model-predicted demand values (aligned with actual).
        seasonality: Lag for the naive forecast (default 1 = lag-1 naive).

    Returns:
        MASE as a float >= 0. Values < 1.0 mean better than naive. 0 is perfect.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    mae_model = np.mean(np.abs(actual - predicted))

    naive_errors = np.abs(actual[seasonality:] - actual[:-seasonality])
    mae_naive = np.mean(naive_errors) if len(naive_errors) > 0 else 1.0

    if mae_naive == 0:
        return 0.0

    return float(mae_model / mae_naive)
