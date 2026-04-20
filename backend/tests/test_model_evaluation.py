import pandas as pd

from ml.evaluation import evaluate_predictions


def test_evaluate_predictions_returns_global_and_segment_metrics():
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "A", "quantity": 10, "predicted_qty": 9, "is_promotional": 1},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "A", "quantity": 11, "predicted_qty": 12, "is_promotional": 0},
            {"date": "2026-01-03", "store_id": "S1", "product_id": "B", "quantity": 0, "predicted_qty": 1, "is_promotional": 0},
            {"date": "2026-01-04", "store_id": "S1", "product_id": "B", "quantity": 0, "predicted_qty": 0, "is_promotional": 0},
            {"date": "2026-01-05", "store_id": "S2", "product_id": "C", "quantity": 2, "predicted_qty": 2, "is_promotional": 0, "is_perishable": 1},
            {"date": "2026-01-06", "store_id": "S2", "product_id": "C", "quantity": 3, "predicted_qty": 2, "is_promotional": 0, "is_stockout": 1},
        ]
    )
    report = evaluate_predictions(frame, min_segment_rows=5)
    assert "global_metrics" in report
    assert "segment_metrics" in report
    assert report["segment_metrics"]["promoted"]["available"] is True
    assert report["segment_metrics"]["promoted"]["low_sample"] is True
    assert "mae" in report["segment_metrics"]["promoted"]["metrics"]


def test_evaluate_predictions_handles_missing_optional_segment_fields():
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "A", "quantity": 10, "predicted_qty": 9},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "A", "quantity": 11, "predicted_qty": 12},
            {"date": "2026-01-03", "store_id": "S2", "product_id": "B", "quantity": 2, "predicted_qty": 2},
        ]
    )
    report = evaluate_predictions(frame, min_segment_rows=2)
    assert report["segment_metrics"]["perishable"]["available"] is False
    assert report["segment_metrics"]["stockout_window"]["available"] is False
