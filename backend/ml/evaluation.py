from __future__ import annotations

import pandas as pd

from ml.metrics_contract import compute_forecast_metrics
from ml.segments import infer_segments


def evaluate_predictions(
    frame: pd.DataFrame,
    *,
    actual_col: str = "quantity",
    predicted_col: str = "predicted_qty",
    min_segment_rows: int = 20,
) -> dict:
    if actual_col not in frame.columns or predicted_col not in frame.columns:
        raise ValueError(f"evaluate_predictions requires '{actual_col}' and '{predicted_col}' columns")

    global_metrics = compute_forecast_metrics(frame[actual_col], frame[predicted_col])
    memberships = infer_segments(frame)
    segment_metrics: dict[str, dict] = {}

    for segment_name, mask in memberships.items():
        count = int(mask.sum())
        if count == 0:
            segment_metrics[segment_name] = {
                "available": False,
                "sample_rows": 0,
                "low_sample": False,
                "metrics": None,
            }
            continue

        subset = frame.loc[mask].copy()
        segment_metrics[segment_name] = {
            "available": True,
            "sample_rows": count,
            "low_sample": count < min_segment_rows,
            "metrics": compute_forecast_metrics(subset[actual_col], subset[predicted_col]),
        }

    return {
        "global_metrics": global_metrics,
        "segment_metrics": segment_metrics,
    }
