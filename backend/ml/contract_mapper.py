"""Profile-driven mapping and validation into canonical transaction contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from ml.contract_profiles import ContractProfile

CANONICAL_REQUIRED_FIELDS = ["date", "store_id", "product_id", "quantity"]
CANONICAL_METADATA_FIELDS = ["tenant_id", "source_type", "frequency", "country_code"]
CANONICAL_OPTIONAL_FIELDS = [
    "unit_cost",
    "unit_price",
    "on_hand_qty",
    "on_order_qty",
    "is_promotional",
    "is_holiday",
    "category",
]
CANONICAL_ALL_FIELDS = CANONICAL_REQUIRED_FIELDS + CANONICAL_METADATA_FIELDS + CANONICAL_OPTIONAL_FIELDS

DEFAULT_THRESHOLDS = {
    "min_date_parse_success": 0.99,
    "max_required_null_rate": 0.005,
    "max_duplicate_rate": 0.01,
    "min_quantity_parse_success": 0.995,
    "max_future_days": 7,
    "max_history_years": 15,
    "max_store_ref_missing_rate": 0.0,
    "max_product_ref_missing_rate": 0.0,
}


@dataclass
class ValidationReport:
    passed: bool
    thresholds: dict[str, float]
    metrics: dict[str, float]
    failures: list[str]
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "thresholds": self.thresholds,
            "metrics": self.metrics,
            "failures": self.failures,
            "row_count": self.row_count,
        }


@dataclass
class CanonicalResult:
    dataframe: pd.DataFrame
    report: ValidationReport


def _parse_bool(value: Any) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, bool):
        return int(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return 1
    if text in {"0", "false", "f", "no", "n", ""}:
        return 0
    return 0


def _coerce_type(series: pd.Series, target_type: str) -> pd.Series:
    t = target_type.lower()
    if t in {"str", "string"}:
        return series.astype("string")
    if t == "int":
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    if t == "float":
        return pd.to_numeric(series, errors="coerce")
    if t == "date":
        return pd.to_datetime(series, errors="coerce")
    if t == "bool":
        return series.apply(_parse_bool).astype("Int64")
    return series


def _apply_unit_map(df: pd.DataFrame, unit_map: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    for field, spec in unit_map.items():
        if field not in out.columns:
            continue

        if isinstance(spec, (int, float)):
            out[field] = pd.to_numeric(out[field], errors="coerce") * float(spec)
            continue

        if not isinstance(spec, dict):
            continue

        # Supported keys:
        # - multiplier: float
        # - divide_by: float
        multiplier = spec.get("multiplier", 1.0)
        divide_by = spec.get("divide_by")
        series = pd.to_numeric(out[field], errors="coerce")
        series = series * float(multiplier)
        if divide_by not in (None, 0, 0.0):
            series = series / float(divide_by)
        out[field] = series

    return out


def _thresholds(profile: ContractProfile) -> dict[str, float]:
    t = dict(DEFAULT_THRESHOLDS)
    t.update(profile.dq_thresholds or {})
    return t


def _normalize_date(value: Any, profile: ContractProfile) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT

    handling = profile.timezone_handling
    if handling == "source_local_date":
        return pd.Timestamp(ts).normalize()

    if handling == "utc_date":
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return pd.Timestamp(ts.date())

    # convert_to_profile_tz_date
    target_tz = ZoneInfo(profile.timezone)
    if ts.tzinfo is None:
        ts = ts.tz_localize(target_tz)
    else:
        ts = ts.tz_convert(target_tz)
    return pd.Timestamp(ts.date())


def _apply_quantity_sign_policy(mapped: pd.DataFrame, profile: ContractProfile) -> pd.DataFrame:
    if "quantity" not in mapped.columns:
        return mapped

    out = mapped.copy()
    policy = profile.quantity_sign_policy
    quantity = pd.to_numeric(out["quantity"], errors="coerce")

    if policy in {"non_negative", "clip_negative"}:
        out["quantity"] = quantity.clip(lower=0)
        return out

    # allow_negative_returns
    if "transaction_type" in out.columns:
        tx_type = out["transaction_type"].astype("string").str.lower()
        return_mask = tx_type.isin(["return", "refund", "rma"])
        quantity = quantity.copy()
        quantity.loc[return_mask] = -quantity.loc[return_mask].abs()
        sale_mask = tx_type.isin(["sale", "purchase", "sold"])
        quantity.loc[sale_mask] = quantity.loc[sale_mask].abs()
        out["quantity"] = quantity
    else:
        out["quantity"] = quantity
    return out


def _apply_id_normalization(mapped: pd.DataFrame, profile: ContractProfile) -> pd.DataFrame:
    rules = profile.id_normalization_rules or {}
    if not isinstance(rules, dict):
        return mapped
    out = mapped.copy()
    for canonical_field in ("store_id", "product_id"):
        if canonical_field not in out.columns:
            continue
        field_rules = rules.get(canonical_field)
        if not isinstance(field_rules, dict):
            continue
        series = out[canonical_field].astype("string")
        if field_rules.get("strip", True):
            series = series.str.strip()
        if field_rules.get("upper", False):
            series = series.str.upper()
        if field_rules.get("lower", False):
            series = series.str.lower()
        prefix = field_rules.get("remove_prefix")
        if isinstance(prefix, str) and prefix:
            series = series.str.removeprefix(prefix)
        out[canonical_field] = series
    return out


def _representability_failures(raw_df: pd.DataFrame, profile: ContractProfile) -> list[str]:
    failures: list[str] = []

    for required in CANONICAL_REQUIRED_FIELDS:
        mapped_sources = [src for src, target in profile.field_map.items() if target == required]
        source_present = any(src in raw_df.columns for src in mapped_sources)
        canonical_present = required in raw_df.columns
        if not source_present and not canonical_present:
            failures.append(f"requires_custom_adapter: missing mapping/source for required field '{required}'")

    for source_col in profile.field_map.keys():
        if source_col not in raw_df.columns:
            continue
        sample = raw_df[source_col].dropna().head(100)
        has_nested = sample.apply(lambda v: isinstance(v, (dict, list, tuple, set))).any()
        if bool(has_nested):
            failures.append(
                "requires_custom_adapter: nested/object values detected in "
                f"'{source_col}' (flattening logic not representable via profile mapping)"
            )

    return failures


def _reference_ids(reference_data: dict[str, pd.DataFrame], key: str) -> set[str]:
    frame = reference_data.get(key)
    if frame is None or frame.empty:
        return set()

    if key == "stores":
        candidate_cols = ["store_id", "store_code", "location_id", "STORE_NBR", "STORE_ID"]
    else:
        candidate_cols = ["product_id", "sku", "item_nbr", "ITEM_NBR", "SKU", "GTIN", "upc", "UPC"]

    for col in candidate_cols:
        if col in frame.columns:
            return {str(v) for v in frame[col].dropna().astype("string").tolist()}
    return set()


def map_to_canonical(raw_df: pd.DataFrame, profile: ContractProfile) -> pd.DataFrame:
    """Map arbitrary tenant schema into canonical transaction fields."""
    if raw_df.empty:
        return pd.DataFrame(columns=CANONICAL_ALL_FIELDS)

    mapped = raw_df.rename(columns=profile.field_map).copy()

    # Ensure required fields exist for subsequent coercion/validation.
    for field in CANONICAL_REQUIRED_FIELDS:
        if field not in mapped.columns:
            mapped[field] = pd.NA

    # Apply type coercion rules.
    for field, type_name in profile.type_map.items():
        if field in mapped.columns:
            mapped[field] = _coerce_type(mapped[field], type_name)

    # Apply null policies (fill values for optional fields).
    for field, policy in profile.null_policy.items():
        if field not in mapped.columns:
            continue
        if isinstance(policy, dict):
            if "fill_value" in policy:
                mapped[field] = mapped[field].fillna(policy["fill_value"])
        elif policy is not None:
            mapped[field] = mapped[field].fillna(policy)

    mapped = _apply_unit_map(mapped, profile.unit_map)

    # Canonical metadata.
    mapped["tenant_id"] = profile.tenant_id
    mapped["source_type"] = profile.source_type
    mapped["frequency"] = profile.grain
    mapped["country_code"] = profile.country_code

    # Default optional fields.
    if "is_promotional" not in mapped.columns:
        mapped["is_promotional"] = 0
    if "is_holiday" not in mapped.columns:
        mapped["is_holiday"] = 0

    for field in ["store_id", "product_id", "category"]:
        if field in mapped.columns:
            mapped[field] = mapped[field].astype("string")
    mapped = _apply_id_normalization(mapped, profile)

    # Quantity + optional numerics should be numeric for downstream pipelines.
    for field in ["quantity", "unit_cost", "unit_price", "on_hand_qty", "on_order_qty"]:
        if field in mapped.columns:
            mapped[field] = pd.to_numeric(mapped[field], errors="coerce")
    mapped = _apply_quantity_sign_policy(mapped, profile)

    for field in ["is_promotional", "is_holiday"]:
        if field in mapped.columns:
            mapped[field] = mapped[field].apply(_parse_bool).astype(int)

    if "date" in mapped.columns:
        mapped["date"] = mapped["date"].apply(lambda value: _normalize_date(value, profile))

    for field in CANONICAL_ALL_FIELDS:
        if field not in mapped.columns:
            mapped[field] = pd.NA

    return mapped[CANONICAL_ALL_FIELDS]


def validate_canonical(
    canonical_df: pd.DataFrame,
    profile: ContractProfile,
    reference_data: dict[str, pd.DataFrame] | None = None,
) -> ValidationReport:
    """Validate canonical data against strict onboarding thresholds."""
    thresholds = _thresholds(profile)

    row_count = len(canonical_df)
    if row_count == 0:
        return ValidationReport(
            passed=False,
            thresholds=thresholds,
            metrics={
                "date_parse_success": 0.0,
                "required_null_rate": 1.0,
                "duplicate_rate": 0.0,
                "quantity_parse_success": 0.0,
                "max_future_days_observed": 0.0,
                "history_years_observed": 0.0,
                "store_ref_missing_rate": 0.0,
                "product_ref_missing_rate": 0.0,
            },
            failures=["No rows available after mapping"],
            row_count=0,
        )

    date_parse_success = float(canonical_df["date"].notna().mean())
    quantity_parse_success = float(canonical_df["quantity"].notna().mean())

    required_null_rates = [float(canonical_df[col].isna().mean()) for col in CANONICAL_REQUIRED_FIELDS]
    required_null_rate = float(np.mean(required_null_rates))

    dedupe_keys = [k for k in profile.dedupe_keys if k in canonical_df.columns]
    duplicate_rate = float(canonical_df.duplicated(subset=dedupe_keys).mean()) if dedupe_keys else 0.0

    today = datetime.now(timezone.utc).date()
    max_date = pd.to_datetime(canonical_df["date"], errors="coerce").dropna().max()
    min_date = pd.to_datetime(canonical_df["date"], errors="coerce").dropna().min()
    max_future_days_observed = 0.0
    history_years_observed = 0.0
    if pd.notna(max_date):
        max_future_days_observed = float((max_date.date() - today).days)
    if pd.notna(min_date):
        history_years_observed = float((today - min_date.date()).days / 365.0)

    store_ref_missing_rate = 0.0
    product_ref_missing_rate = 0.0
    if reference_data:
        store_ref = _reference_ids(reference_data, "stores")
        product_ref = _reference_ids(reference_data, "products")

        if store_ref:
            store_ids = canonical_df["store_id"].dropna().astype("string")
            store_ref_missing_rate = float((~store_ids.isin(store_ref)).mean())
        if product_ref:
            product_ids = canonical_df["product_id"].dropna().astype("string")
            product_ref_missing_rate = float((~product_ids.isin(product_ref)).mean())

    metrics = {
        "date_parse_success": date_parse_success,
        "required_null_rate": required_null_rate,
        "duplicate_rate": duplicate_rate,
        "quantity_parse_success": quantity_parse_success,
        "max_future_days_observed": max_future_days_observed,
        "history_years_observed": history_years_observed,
        "store_ref_missing_rate": store_ref_missing_rate,
        "product_ref_missing_rate": product_ref_missing_rate,
    }

    failures: list[str] = []
    if date_parse_success < thresholds["min_date_parse_success"]:
        failures.append(
            f"date_parse_success={date_parse_success:.4f} below min_date_parse_success={thresholds['min_date_parse_success']:.4f}"
        )
    if required_null_rate > thresholds["max_required_null_rate"]:
        failures.append(
            f"required_null_rate={required_null_rate:.4f} above max_required_null_rate={thresholds['max_required_null_rate']:.4f}"
        )
    if duplicate_rate > thresholds["max_duplicate_rate"]:
        failures.append(
            f"duplicate_rate={duplicate_rate:.4f} above max_duplicate_rate={thresholds['max_duplicate_rate']:.4f}"
        )
    if quantity_parse_success < thresholds["min_quantity_parse_success"]:
        failures.append(
            f"quantity_parse_success={quantity_parse_success:.4f} below min_quantity_parse_success={thresholds['min_quantity_parse_success']:.4f}"
        )
    if max_future_days_observed > thresholds["max_future_days"]:
        failures.append(
            f"max_future_days_observed={max_future_days_observed:.1f} above max_future_days={thresholds['max_future_days']:.1f}"
        )
    if history_years_observed > thresholds["max_history_years"]:
        failures.append(
            f"history_years_observed={history_years_observed:.2f} above max_history_years={thresholds['max_history_years']:.2f}"
        )
    if store_ref_missing_rate > thresholds["max_store_ref_missing_rate"]:
        failures.append(
            "store_ref_missing_rate="
            f"{store_ref_missing_rate:.4f} above max_store_ref_missing_rate={thresholds['max_store_ref_missing_rate']:.4f}"
        )
    if product_ref_missing_rate > thresholds["max_product_ref_missing_rate"]:
        failures.append(
            "product_ref_missing_rate="
            f"{product_ref_missing_rate:.4f} above max_product_ref_missing_rate={thresholds['max_product_ref_missing_rate']:.4f}"
        )

    return ValidationReport(
        passed=not failures,
        thresholds=thresholds,
        metrics=metrics,
        failures=failures,
        row_count=row_count,
    )


def build_canonical_result(
    raw_df: pd.DataFrame,
    profile: ContractProfile,
    reference_data: dict[str, pd.DataFrame] | None = None,
) -> CanonicalResult:
    """Map and validate in one call for onboarding flows."""
    representability_failures = _representability_failures(raw_df, profile)
    canonical = map_to_canonical(raw_df, profile)
    report = validate_canonical(canonical, profile, reference_data=reference_data)
    merged_failures = representability_failures + report.failures
    merged_metrics = dict(report.metrics)
    merged_metrics["requires_custom_adapter"] = 1.0 if representability_failures else 0.0
    report = ValidationReport(
        passed=not merged_failures,
        thresholds=report.thresholds,
        metrics=merged_metrics,
        failures=merged_failures,
        row_count=report.row_count,
    )
    return CanonicalResult(dataframe=canonical, report=report)
