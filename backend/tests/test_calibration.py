import numpy as np

from ml.calibration import calibration_summary, conformal_interval, conformal_residual_quantile


def test_conformal_residual_quantile_non_negative():
    q = conformal_residual_quantile(np.array([10, 12, 14]), np.array([9, 11, 15]), alpha=0.1)
    assert q >= 0


def test_conformal_interval_and_summary():
    preds = np.array([10.0, 12.0, 14.0])
    lower, upper = conformal_interval(preds, 2.0)
    summary = calibration_summary(np.array([11.0, 13.0, 15.0]), lower, upper)
    assert (lower <= preds).all()
    assert (upper >= preds).all()
    assert 0.0 <= summary["coverage"] <= 1.0
