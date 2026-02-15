"""Profile-driven mapping and validation into canonical transaction contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

    # Quantity + optional numerics should be numeric for downstream pipelines.
    for field in ["quantity", "unit_cost", "unit_price", "on_hand_qty", "on_order_qty"]:
        if field in mapped.columns:
            mapped[field] = pd.to_numeric(mapped[field], errors="coerce")

    for field in ["is_promotional", "is_holiday"]:
        if field in mapped.columns:
            mapped[field] = mapped[field].apply(_parse_bool).astype(int)

    if "date" in mapped.columns:
        mapped["date"] = pd.to_datetime(mapped["date"], errors="coerce")

    for field in CANONICAL_ALL_FIELDS:
        if field not in mapped.columns:
            mapped[field] = pd.NA

    return mapped[CANONICAL_ALL_FIELDS]


def validate_canonical(canonical_df: pd.DataFrame, profile: ContractProfile) -> ValidationReport:
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

    metrics = {
        "date_parse_success": date_parse_success,
        "required_null_rate": required_null_rate,
        "duplicate_rate": duplicate_rate,
        "quantity_parse_success": quantity_parse_success,
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

    return ValidationReport(
        passed=not failures,
        thresholds=thresholds,
        metrics=metrics,
        failures=failures,
        row_count=row_count,
    )


def build_canonical_result(raw_df: pd.DataFrame, profile: ContractProfile) -> CanonicalResult:
    """Map and validate in one call for onboarding flows."""
    canonical = map_to_canonical(raw_df, profile)
    report = validate_canonical(canonical, profile)
    return CanonicalResult(dataframe=canonical, report=report)
