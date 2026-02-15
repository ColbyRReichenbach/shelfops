import pandas as pd

from ml.metrics_contract import compute_forecast_metrics, coverage_rate


def test_metrics_contract_values_are_deterministic():
    y_true = pd.Series([10.0, 0.0, 5.0])
    y_pred = pd.Series([8.0, 2.0, 0.0])

    metrics = compute_forecast_metrics(y_true, y_pred)

    assert round(float(metrics["mae"]), 6) == 3.0
    assert round(float(metrics["mape_nonzero"]), 6) == 0.6
    assert round(float(metrics["stockout_miss_rate"]), 6) == round(1 / 3, 6)
    assert round(float(metrics["overstock_rate"]), 6) == round(1 / 3, 6)


def test_overstock_dollars_returns_unavailable_without_cost_basis():
    y_true = pd.Series([10.0, 0.0, 5.0])
    y_pred = pd.Series([8.0, 2.0, 0.0])
    metrics = compute_forecast_metrics(y_true, y_pred)
    assert metrics["overstock_dollars"] is None
    assert metrics["overstock_dollars_confidence"] == "unavailable"


def test_overstock_dollars_with_measured_cost_basis():
    y_true = pd.Series([10.0, 0.0, 5.0])
    y_pred = pd.Series([8.0, 2.0, 0.0])
    unit_cost = pd.Series([2.0, 2.0, 1.0])
    metrics = compute_forecast_metrics(y_true, y_pred, unit_cost=unit_cost)
    assert float(metrics["overstock_dollars"]) == 4.0
    assert metrics["overstock_dollars_confidence"] == "measured"


def test_coverage_rate():
    y_true = [10, 8, 12, 6]
    lower = [9, 9, 10, 7]
    upper = [11, 11, 13, 9]
    assert coverage_rate(y_true, lower, upper) == 0.5
