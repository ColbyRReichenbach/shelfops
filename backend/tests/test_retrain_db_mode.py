from datetime import date, timedelta

import pandas as pd
import pytest

from workers.retrain import _apply_training_cutoff, _load_db_data


def test_load_db_data_no_data_path_blocks():
    raw = pd.DataFrame(columns=["date", "store_id", "product_id", "quantity"])
    with pytest.raises(ValueError, match="No transaction history"):
        _load_db_data("00000000-0000-0000-0000-000000000001", raw_override=raw)


def test_load_db_data_partial_data_blocks():
    raw = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "P1", "quantity": 5},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "P1", "quantity": 7},
        ]
    )
    with pytest.raises(ValueError, match="Insufficient training rows"):
        _load_db_data("00000000-0000-0000-0000-000000000001", min_rows=10, raw_override=raw)


def test_load_db_data_valid_path_returns_canonical_dataframe():
    rows = []
    start = date.today() - timedelta(days=130)
    for day in range(1, 121):
        current = start + timedelta(days=day)
        rows.append(
            {
                "date": current.isoformat(),
                "store_id": "S1",
                "product_id": f"P{day % 5}",
                "quantity": float((day % 7) + 1),
                "category": "general",
                "unit_cost": 2.5,
                "unit_price": 5.0,
                "is_promotional": 0,
                "is_holiday": 0,
            }
        )

    out = _load_db_data(
        "00000000-0000-0000-0000-000000000001",
        min_rows=90,
        raw_override=pd.DataFrame(rows),
    )
    assert len(out) >= 90
    assert {"date", "store_id", "product_id", "quantity", "tenant_id", "source_type", "frequency"}.issubset(out.columns)


def test_load_db_data_applies_return_sign_policy_from_contract():
    raw = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "store_id": "S1",
                "product_id": "P1",
                "quantity": 5,
                "transaction_type": "sale",
            },
            {
                "date": "2026-01-02",
                "store_id": "S1",
                "product_id": "P1",
                "quantity": 2,
                "transaction_type": "return",
            },
        ]
    )
    out = _load_db_data(
        "00000000-0000-0000-0000-000000000001",
        min_rows=2,
        raw_override=raw,
    )
    assert out["quantity"].iloc[0] == 5
    assert out["quantity"].iloc[1] == -2


def test_apply_training_cutoff_filters_future_rows():
    raw = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "P1", "quantity": 5},
            {"date": "2026-01-10", "store_id": "S1", "product_id": "P1", "quantity": 6},
            {"date": "2026-01-20", "store_id": "S1", "product_id": "P1", "quantity": 7},
        ]
    )
    filtered, cutoff = _apply_training_cutoff(raw, "2026-01-10")
    assert cutoff == "2026-01-10"
    assert len(filtered) == 2
    assert pd.to_datetime(filtered["date"]).max().date().isoformat() == "2026-01-10"
