from __future__ import annotations

import numpy as np


def symmetric_quantile_band(y_pred: np.ndarray, *, residual_scale: float, confidence_level: float) -> tuple[np.ndarray, np.ndarray]:
    pred = np.asarray(y_pred, dtype=float)
    band = float(max(residual_scale, 0.0))
    lower = np.maximum(pred - band, 0.0)
    upper = pred + band
    return lower, upper
