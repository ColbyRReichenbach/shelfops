from pathlib import Path

from scripts import run_onboarding_flow


def test_run_onboarding_flow_orchestrates_pipeline(tmp_path: Path, monkeypatch):
    contract = tmp_path / "v1.yaml"
    contract.write_text(
        """
contract_version: v1
tenant_id: tenant-1
source_type: smb_csv
grain: daily
timezone: America/New_York
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

    # Lightweight stubs so this test verifies orchestration only.
    monkeypatch.setattr(
        run_onboarding_flow,
        "_load_profiled_data",
        lambda contract_path, sample_path, output_dir: __import__("pandas").DataFrame(
            [{"date": "2026-01-01", "store_id": "S1", "product_id": "SKU1", "quantity": 5}]
        ),
    )
    monkeypatch.setattr(
        run_onboarding_flow,
        "create_features",
        lambda transactions_df, force_tier=None: transactions_df.assign(
            quantity=transactions_df["quantity"].astype(float)
        ),
    )
    monkeypatch.setattr(
        run_onboarding_flow,
        "train_ensemble",
        lambda features_df, dataset_name, version: {"xgboost": {"metrics": {"mae": 1.0, "mape": 0.1}}},
    )
    monkeypatch.setattr(
        run_onboarding_flow, "save_models", lambda ensemble_result, version, dataset_name, promote: None
    )
    monkeypatch.setattr(run_onboarding_flow, "_next_version", lambda: "v-test")

    monkeypatch.setattr(
        "sys.argv",
        [
            "run_onboarding_flow.py",
            "--contract",
            str(contract),
            "--sample-path",
            str(sample),
            "--canonical-output-dir",
            str(tmp_path / "canonical"),
        ],
    )

    rc = run_onboarding_flow.main()
    assert rc == 0
