import pandas as pd

from scripts.benchmark_datasets import BUSINESS_METRIC_NOT_AVAILABLE, _safe_metrics, render_markdown


def test_safe_metrics_marks_m5_business_metrics_not_available():
    y_true = pd.Series([1.0, 2.0, 3.0, 4.0])
    preds = pd.Series([1.0, 2.0, 2.5, 4.5])
    metrics = _safe_metrics("m5_walmart", y_true, preds)
    for key, value in BUSINESS_METRIC_NOT_AVAILABLE.items():
        assert metrics[key] == value
    assert metrics["wape"] >= 0
    assert metrics["mase"] >= 0


def test_render_markdown_contains_lightgbm_and_baselines():
    report = {
        "dataset_id": "m5_walmart",
        "rows_used": 100,
        "date_min": "2026-01-01",
        "date_max": "2026-03-31",
        "results": [
            {
                "model_name": "naive",
                "mae": 1.2,
                "wape": 0.2,
                "mase": 1.1,
                "bias_pct": 0.01,
                "interval_method": "not_available",
                "stockout_miss_rate": "not_available",
                "overstock_rate": "not_available",
                "rows_test": 20,
            },
            {
                "model_name": "lightgbm",
                "mae": 0.8,
                "wape": 0.15,
                "mase": 0.9,
                "bias_pct": -0.02,
                "interval_method": "not_available",
                "stockout_miss_rate": "not_available",
                "overstock_rate": "not_available",
                "rows_test": 20,
            },
        ],
    }
    md = render_markdown(report)
    assert "| naive |" in md
    assert "| lightgbm |" in md
    assert "dataset_id: `m5_walmart`" in md
