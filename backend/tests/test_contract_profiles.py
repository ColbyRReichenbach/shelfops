from pathlib import Path

import pytest

from ml.contract_profiles import ContractProfileError, load_contract_profile


def test_load_contract_profile_valid(tmp_path: Path):
    path = tmp_path / "v1.yaml"
    path.write_text(
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

    profile = load_contract_profile(path)
    assert profile.contract_version == "v1"
    assert profile.source_type == "smb_csv"


def test_load_contract_profile_missing_required_key(tmp_path: Path):
    path = tmp_path / "v1.yaml"
    path.write_text(
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
""",
        encoding="utf-8",
    )

    with pytest.raises(ContractProfileError):
        load_contract_profile(path)


def test_load_contract_profile_unknown_source_type(tmp_path: Path):
    path = tmp_path / "v1.yaml"
    path.write_text(
        """
contract_version: v1
tenant_id: tenant-1
source_type: weird_source
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

    with pytest.raises(ContractProfileError):
        load_contract_profile(path)
