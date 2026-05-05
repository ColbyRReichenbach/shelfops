from pathlib import Path

import pandas as pd
import pytest

from ml.data_contracts import inspect_dataset_readiness, load_canonical_transactions
from workers.retrain import _load_csv_data


def test_load_favorita_contract(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "date": "2024-01-01",
                "store_nbr": 1,
                "family": "GROCERY",
                "sales": 12.0,
                "onpromotion": 1,
            },
            {
                "id": 2,
                "date": "2024-01-02",
                "store_nbr": 1,
                "family": "GROCERY",
                "sales": 10.0,
                "onpromotion": 0,
            },
        ]
    )
    df.to_csv(tmp_path / "train.csv", index=False)
    pd.DataFrame([{"date": "2024-01-01", "type": "Holiday"}]).to_csv(tmp_path / "holidays_events.csv", index=False)

    out = load_canonical_transactions(str(tmp_path))
    assert set(["date", "store_id", "product_id", "quantity"]).issubset(out.columns)
    assert out["dataset_id"].iloc[0] == "favorita"
    assert out["country_code"].iloc[0] == "EC"
    assert out["frequency"].iloc[0] == "daily"

    readiness = inspect_dataset_readiness(tmp_path)
    assert readiness.status in {"ready", "limited"}
    assert readiness.forecast_grain == "store_nbr x family x date"


def test_load_walmart_contract(tmp_path: Path):
    train = pd.DataFrame(
        [
            {"Store": 1, "Dept": 7, "Date": "2012-01-06", "Weekly_Sales": 1000.0, "IsHoliday": False},
            {"Store": 1, "Dept": 7, "Date": "2012-01-13", "Weekly_Sales": -1100.0, "IsHoliday": True},
        ]
    )
    train.to_csv(tmp_path / "train.csv", index=False)
    pd.DataFrame([{"Store": 1, "Type": "A", "Size": 151315}]).to_csv(tmp_path / "stores.csv", index=False)
    pd.DataFrame([{"Store": 1, "Date": "2012-01-06", "Temperature": 42.0}]).to_csv(
        tmp_path / "features.csv", index=False
    )

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "walmart"
    assert out["country_code"].iloc[0] == "US"
    assert out["frequency"].iloc[0] == "weekly"
    assert out["category"].iloc[0] == "7"
    assert out["quantity"].min() >= 0
    assert out["is_return_week"].sum() == 1
    assert out["returns_adjustment"].min() < 0


def test_load_rossmann_contract(tmp_path: Path):
    train = pd.DataFrame(
        [
            {"Store": 1, "Date": "2015-07-31", "Sales": 5263, "Promo": 1},
            {"Store": 1, "Date": "2015-08-01", "Sales": 5020, "Promo": 0},
        ]
    )
    train.to_csv(tmp_path / "train.csv", index=False)
    pd.DataFrame([{"Store": 1, "StoreType": "a"}]).to_csv(tmp_path / "store.csv", index=False)

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "rossmann"
    assert out["country_code"].iloc[0] == "DE"
    assert out["frequency"].iloc[0] == "daily"
    assert out["product_id"].nunique() == 1
    assert out["product_grain"].iloc[0] == "store_level_only"


def test_load_seed_transaction_contract(tmp_path: Path):
    tx_dir = tmp_path / "transactions"
    tx_dir.mkdir(parents=True, exist_ok=True)
    tx = pd.DataFrame(
        [
            {"STORE_NBR": "STR-001", "ITEM_NBR": "SKU-1", "QTY_SOLD": 5, "TRANS_DATE": "2025-08-20"},
            {"STORE_NBR": "STR-001", "ITEM_NBR": "SKU-2", "QTY_SOLD": 7, "TRANS_DATE": "2025-08-20"},
        ]
    )
    tx.to_csv(tx_dir / "DAILY_SALES_20250820.csv", index=False)

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "seed_synthetic"
    assert out["frequency"].iloc[0] == "daily"
    assert out["product_id"].nunique() == 2


def test_generic_flat_csv_ignores_lookup_only_files(tmp_path: Path):
    pd.DataFrame([{"store_id": "A", "city": "X"}]).to_csv(tmp_path / "stores.csv", index=False)
    pd.DataFrame(
        [
            {"date": "2024-01-01", "store_id": "A", "quantity": 2, "category": "General"},
            {"date": "2024-01-02", "store_id": "A", "quantity": 3, "category": "General"},
        ]
    ).to_csv(tmp_path / "transactions.csv", index=False)

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "generic"
    assert len(out) == 2


def test_load_canonical_transactions_prefers_prepared_canonical_csv(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "store_id": "S1",
                "product_id": "SKU1",
                "quantity": 5,
                "category": "FOODS",
                "dataset_id": "m5_walmart",
                "country_code": "US",
                "frequency": "daily",
            }
        ]
    ).to_csv(tmp_path / "canonical_transactions.csv", index=False)
    # Conflicting raw-looking file should not override the prepared canonical output.
    pd.DataFrame([{"date": "2024-01-01", "store_id": "S1", "quantity": 1}]).to_csv(
        tmp_path / "transactions.csv", index=False
    )

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "m5_walmart"
    assert out["country_code"].iloc[0] == "US"
    assert out["frequency"].iloc[0] == "daily"


def test_load_freshretailnet_contract(tmp_path: Path):
    frame = pd.DataFrame(
        [
            {
                "city_id": 1,
                "store_id": 101,
                "management_group_id": 10,
                "first_category_id": 100,
                "second_category_id": 110,
                "third_category_id": 111,
                "product_id": 999,
                "dt": "2024-03-30",
                "sale_amount": 12.0,
                "hours_sale": [0.0] * 24,
                "stock_hour6_22_cnt": 2,
                "hours_stock_status": [0] * 24,
                "discount": 0.95,
                "holiday_flag": 0,
                "activity_flag": 0,
                "precpt": 1.2,
                "avg_temperature": 15.0,
                "avg_humidity": 77.0,
                "avg_wind_level": 1.1,
            }
        ]
    )
    frame.to_parquet(tmp_path / "train.parquet", index=False)
    frame.to_parquet(tmp_path / "eval.parquet", index=False)

    readiness = inspect_dataset_readiness(tmp_path)
    assert readiness.dataset_id == "freshretailnet_50k"
    assert readiness.status == "ready"

    out = load_canonical_transactions(str(tmp_path))
    assert out["dataset_id"].iloc[0] == "freshretailnet_50k"
    assert out["frequency"].iloc[0] == "daily"
    assert "stockout_window" in out.columns


def test_retrain_loader_uses_canonical_contract(tmp_path: Path):
    pd.DataFrame(
        [
            {
                "id": 1,
                "date": "2024-01-01",
                "store_nbr": 1,
                "family": "GROCERY",
                "sales": 5.0,
                "onpromotion": 0,
            }
        ]
    ).to_csv(tmp_path / "train.csv", index=False)
    pd.DataFrame([{"date": "2024-01-01", "type": "Holiday"}]).to_csv(tmp_path / "holidays_events.csv", index=False)

    out = _load_csv_data(str(tmp_path))
    assert set(["date", "store_id", "product_id", "quantity", "dataset_id", "country_code", "frequency"]).issubset(
        out.columns
    )


def test_favorita_loader_fails_clearly_when_train_missing(tmp_path: Path):
    (tmp_path / "holidays_events.csv").write_text("date,type\n2024-01-01,Holiday\n", encoding="utf-8")
    (tmp_path / "transactions.csv").write_text("date,store_nbr,transactions\n2024-01-01,1,100\n", encoding="utf-8")

    readiness = inspect_dataset_readiness(tmp_path)
    assert readiness.dataset_id == "favorita"
    assert readiness.status == "blocked"
    assert "train.csv" in readiness.missing_files

    with pytest.raises(FileNotFoundError, match="Favorita dataset is not ready"):
        load_canonical_transactions(str(tmp_path))


def test_profiled_loader_writes_canonical_csv(tmp_path: Path):
    from workers.retrain import _load_profiled_data

    contract = tmp_path / "v1.yaml"
    contract.write_text(
        """
contract_version: v1
tenant_id: tenant-1
source_type: smb_csv
grain: daily
timezone: America/New_York
timezone_handling: convert_to_profile_tz_date
quantity_sign_policy: non_negative
id_columns: {store: store_id, product: product_id}
field_map: {sale_date: date, store: store_id, sku: product_id, qty: quantity}
type_map: {date: date, store_id: str, product_id: str, quantity: float}
unit_map: {quantity: {multiplier: 1.0}}
null_policy: {}
dedupe_keys: [store_id, product_id, date]
dq_thresholds:
  min_date_parse_success: 0.99
  max_required_null_rate: 0.005
  max_duplicate_rate: 0.01
  min_quantity_parse_success: 0.995
""",
        encoding="utf-8",
    )

    sample = tmp_path / "sample.csv"
    sample.write_text("sale_date,store,sku,qty\n2026-01-01,S1,SKU1,5\n", encoding="utf-8")

    out_dir = tmp_path / "canonical"
    out = _load_profiled_data(str(contract), str(sample), str(out_dir))

    assert len(out) == 1
    assert (out_dir / "canonical_transactions.csv").exists()
    assert (out_dir / "contract_validation_report.json").exists()
    assert (out_dir / "contract_validation_report.md").exists()
