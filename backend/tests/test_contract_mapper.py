import pandas as pd

from ml.contract_mapper import build_canonical_result
from ml.contract_profiles import ContractProfile


def _profile_variant_a() -> ContractProfile:
    return ContractProfile(
        contract_version="v1",
        tenant_id="tenant-parity",
        source_type="smb_csv",
        grain="daily",
        timezone="America/New_York",
        id_columns={"store": "store_id", "product": "product_id"},
        field_map={"sale_date": "date", "store": "store_id", "sku": "product_id", "qty": "quantity"},
        type_map={"date": "date", "store_id": "str", "product_id": "str", "quantity": "float"},
        unit_map={"quantity": {"multiplier": 1.0}},
        null_policy={},
        dedupe_keys=["store_id", "product_id", "date"],
        dq_thresholds={
            "min_date_parse_success": 0.99,
            "max_required_null_rate": 0.005,
            "max_duplicate_rate": 0.01,
            "min_quantity_parse_success": 0.995,
        },
        country_code="US",
    )


def _profile_variant_b() -> ContractProfile:
    return ContractProfile(
        contract_version="v1",
        tenant_id="tenant-parity",
        source_type="smb_sftp",
        grain="daily",
        timezone="America/New_York",
        id_columns={"location_id": "store_id", "item_code": "product_id"},
        field_map={
            "event_date": "date",
            "location_id": "store_id",
            "item_code": "product_id",
            "qty_tens": "quantity",
        },
        type_map={"date": "date", "store_id": "str", "product_id": "str", "quantity": "float"},
        unit_map={"quantity": {"multiplier": 10.0}},
        null_policy={},
        dedupe_keys=["store_id", "product_id", "date"],
        dq_thresholds={
            "min_date_parse_success": 0.99,
            "max_required_null_rate": 0.005,
            "max_duplicate_rate": 0.01,
            "min_quantity_parse_success": 0.995,
        },
        country_code="US",
    )


def test_two_schema_variants_map_to_same_canonical():
    raw_a = pd.read_csv("backend/tests/fixtures/contracts/tenant_a/transactions.csv")
    raw_b = pd.read_csv("backend/tests/fixtures/contracts/tenant_b/transactions.csv")

    result_a = build_canonical_result(raw_a, _profile_variant_a())
    result_b = build_canonical_result(raw_b, _profile_variant_b())
    assert result_a.report.passed is True
    assert result_b.report.passed is True

    out_a = result_a.dataframe
    out_b = result_b.dataframe

    cols = ["date", "store_id", "product_id", "quantity", "tenant_id", "source_type", "frequency"]
    # Source type intentionally differs between variants; compare canonical semantics.
    pd.testing.assert_frame_equal(
        out_a[[c for c in cols if c != "source_type"]],
        out_b[[c for c in cols if c != "source_type"]],
        check_dtype=False,
    )


def test_validation_fails_on_bad_dates_and_duplicates():
    profile = _profile_variant_a()
    raw = pd.DataFrame(
        [
            {"sale_date": "bad", "store": "1", "sku": "A", "qty": 10},
            {"sale_date": "bad", "store": "1", "sku": "A", "qty": 10},
        ]
    )

    result = build_canonical_result(raw, profile)
    assert result.report.passed is False
    assert any("date_parse_success" in f for f in result.report.failures)
