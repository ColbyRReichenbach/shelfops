from pathlib import Path

import pandas as pd

from ml.contract_mapper import build_canonical_result
from ml.contract_profiles import ContractProfile

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "contracts"


def _profile_variant_a() -> ContractProfile:
    return ContractProfile(
        contract_version="v1",
        tenant_id="tenant-parity",
        source_type="smb_csv",
        grain="daily",
        timezone="America/New_York",
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="non_negative",
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
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="non_negative",
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
    raw_a = pd.read_csv(FIXTURE_ROOT / "tenant_a" / "transactions.csv")
    raw_b = pd.read_csv(FIXTURE_ROOT / "tenant_b" / "transactions.csv")

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


def test_quantity_sign_policy_allows_negative_returns_when_transaction_type_present():
    profile = _profile_variant_a()
    profile = ContractProfile(
        **{
            **profile.__dict__,
            "quantity_sign_policy": "allow_negative_returns",
            "field_map": {
                **profile.field_map,
                "txn_type": "transaction_type",
            },
            "type_map": {
                **profile.type_map,
                "transaction_type": "str",
            },
        }
    )
    raw = pd.DataFrame(
        [
            {"sale_date": "2026-01-01", "store": "S1", "sku": "SKU1", "qty": 5, "txn_type": "sale"},
            {"sale_date": "2026-01-02", "store": "S1", "sku": "SKU1", "qty": 2, "txn_type": "return"},
        ]
    )
    result = build_canonical_result(raw, profile)
    assert result.report.passed is True
    quantities = result.dataframe["quantity"].tolist()
    assert quantities == [5.0, -2.0]


def test_timezone_normalization_converts_to_profile_date():
    profile = _profile_variant_a()
    raw = pd.DataFrame(
        [
            # UTC midnight+1 converts to prior calendar date in America/New_York
            {"sale_date": "2026-01-02T01:30:00Z", "store": "S1", "sku": "SKU1", "qty": 3},
        ]
    )
    result = build_canonical_result(raw, profile)
    assert result.report.passed is True
    assert str(result.dataframe.iloc[0]["date"].date()) == "2026-01-01"


def test_reference_integrity_fails_when_product_missing_from_master():
    profile = _profile_variant_a()
    raw = pd.DataFrame(
        [{"sale_date": "2026-01-01", "store": "S1", "sku": "SKU_UNKNOWN", "qty": 3}],
    )
    refs = {
        "stores": pd.DataFrame([{"store_id": "S1"}]),
        "products": pd.DataFrame([{"product_id": "SKU1"}]),
    }
    result = build_canonical_result(raw, profile, reference_data=refs)
    assert result.report.passed is False
    assert any("product_ref_missing_rate" in f for f in result.report.failures)


def test_additional_smb_fixture_variants_map_successfully():
    profile_c = ContractProfile(
        contract_version="v1",
        tenant_id="tenant-c",
        source_type="smb_csv",
        grain="daily",
        timezone="America/New_York",
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="non_negative",
        id_columns={"location": "store_id", "sku_id": "product_id"},
        field_map={
            "sale_dt": "date",
            "location": "store_id",
            "sku_id": "product_id",
            "units_sold": "quantity",
            "cost_usd": "unit_cost",
            "retail_usd": "unit_price",
            "promo": "is_promotional",
        },
        type_map={
            "date": "date",
            "store_id": "str",
            "product_id": "str",
            "quantity": "float",
            "unit_cost": "float",
            "unit_price": "float",
            "is_promotional": "bool",
        },
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
    profile_d = ContractProfile(
        contract_version="v1",
        tenant_id="tenant-d",
        source_type="smb_sftp",
        grain="daily",
        timezone="America/New_York",
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="non_negative",
        id_columns={"STORE_CODE": "store_id", "ITEM_CODE": "product_id"},
        field_map={
            "BUSINESS_DATE": "date",
            "STORE_CODE": "store_id",
            "ITEM_CODE": "product_id",
            "QTY_TENTHS": "quantity",
            "UNIT_COST_CENTS": "unit_cost",
            "UNIT_PRICE_CENTS": "unit_price",
        },
        type_map={
            "date": "date",
            "store_id": "str",
            "product_id": "str",
            "quantity": "float",
            "unit_cost": "float",
            "unit_price": "float",
        },
        unit_map={
            "quantity": {"divide_by": 10.0},
            "unit_cost": {"divide_by": 100.0},
            "unit_price": {"divide_by": 100.0},
        },
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

    raw_c = pd.read_csv(FIXTURE_ROOT / "tenant_c" / "transactions.csv")
    raw_d = pd.read_csv(FIXTURE_ROOT / "tenant_d" / "transactions.csv")

    result_c = build_canonical_result(raw_c, profile_c)
    result_d = build_canonical_result(raw_d, profile_d)
    assert result_c.report.passed is True
    assert result_d.report.passed is True
    assert len(result_c.dataframe) == 2
    assert len(result_d.dataframe) == 2


def test_enterprise_like_fixture_passes_with_reference_data():
    profile = ContractProfile(
        contract_version="v1",
        tenant_id="enterprise-like",
        source_type="enterprise_event",
        grain="daily",
        timezone="UTC",
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="allow_negative_returns",
        id_columns={"store_id": "store_id", "sku": "product_id"},
        field_map={
            "timestamp": "date",
            "store_id": "store_id",
            "sku": "product_id",
            "quantity": "quantity",
            "unit_price": "unit_price",
            "transaction_type": "transaction_type",
        },
        type_map={
            "date": "date",
            "store_id": "str",
            "product_id": "str",
            "quantity": "float",
            "unit_price": "float",
            "transaction_type": "str",
        },
        unit_map={"quantity": {"multiplier": 1.0}},
        null_policy={},
        dedupe_keys=["store_id", "product_id", "date"],
        dq_thresholds={
            "min_date_parse_success": 0.99,
            "max_required_null_rate": 0.005,
            "max_duplicate_rate": 0.01,
            "min_quantity_parse_success": 0.995,
            "max_store_ref_missing_rate": 0.0,
            "max_product_ref_missing_rate": 0.0,
        },
        country_code="US",
    )
    raw = pd.read_csv(FIXTURE_ROOT / "enterprise_like" / "transactions.csv")
    refs = {
        "stores": pd.read_csv(FIXTURE_ROOT / "enterprise_like" / "stores.csv"),
        "products": pd.read_csv(FIXTURE_ROOT / "enterprise_like" / "products.csv"),
    }
    result = build_canonical_result(raw, profile, reference_data=refs)
    assert result.report.passed is True
