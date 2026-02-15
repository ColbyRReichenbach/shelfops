from pathlib import Path

from scripts.validate_customer_contract import main


def test_validate_customer_contract_cli_passes(tmp_path: Path, monkeypatch):
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

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    monkeypatch.setattr(
        "sys.argv",
        [
            "validate_customer_contract.py",
            "--contract",
            str(contract),
            "--sample-path",
            str(sample),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
    )

    rc = main()
    assert rc == 0
    assert out_json.exists()
    assert out_md.exists()
