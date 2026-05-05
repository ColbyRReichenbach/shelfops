import pytest

from ml.stockout_metrics import (
    evaluate_stockout_windows,
    stockout_window_bias,
    underforecast_rate_during_stockouts,
)


def test_stockout_window_bias_uses_only_stockout_rows():
    bias = stockout_window_bias([10, 8, 6], [9, 10, 5], [1, 0, 1])
    assert bias == pytest.approx(-1.0)


def test_underforecast_rate_during_stockouts_uses_stockout_slice():
    rate = underforecast_rate_during_stockouts([10, 8, 6], [9, 10, 5], [1, 0, 1])
    assert rate == pytest.approx(1.0)


def test_evaluate_stockout_windows_reports_non_stockout_error_and_estimated_gap():
    result = evaluate_stockout_windows(
        y_true=[10, 8, 6, 12],
        y_pred=[9, 7, 5, 13],
        stockout_window=[1, 0, 1, 0],
        estimated_recovered_target=[11, 8, 8, 12],
    )
    assert result["stockout_window_rows"] == 2
    assert result["non_stockout_rows"] == 2
    assert result["non_stockout_wape"] is not None
    assert result["estimated_recovered_demand_gap_confidence"] == "estimated"
