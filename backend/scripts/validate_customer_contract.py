#!/usr/bin/env python3
"""Validate a tenant contract against sample source data and emit pass/fail reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ml.contract_mapper import CANONICAL_REQUIRED_FIELDS, build_canonical_result
from ml.contract_profiles import ContractProfileError, load_contract_profile


def _load_sample(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Sample path not found: {path}")

    if path.is_dir():
        preferred_names = ["transactions.csv", "sales.csv", "daily_sales.csv"]
        preferred = [path / name for name in preferred_names if (path / name).exists()]
        if preferred:
            csvs = preferred
        else:
            csvs = sorted(
                p
                for p in path.glob("*.csv")
                if p.name.lower() not in {"stores.csv", "products.csv", "store_master.csv", "product_master.csv"}
            )
        if not csvs:
            raise ValueError(f"No CSV files found under directory: {path}")
        frames = [pd.read_csv(p, low_memory=False) for p in csvs]
        return pd.concat(frames, ignore_index=True)

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, low_memory=False)

    if path.suffix.lower() in {".jsonl", ".json"}:
        return pd.read_json(path, lines=True)

    raise ValueError(f"Unsupported sample file type: {path.suffix}")


def _load_reference_data(sample_path: Path) -> dict[str, pd.DataFrame]:
    if not sample_path.is_dir():
        return {}

    references: dict[str, pd.DataFrame] = {}
    store_candidates = ["stores.csv", "store_master.csv"]
    product_candidates = ["products.csv", "product_master.csv", "items.csv"]

    for name in store_candidates:
        file_path = sample_path / name
        if file_path.exists():
            references["stores"] = pd.read_csv(file_path, low_memory=False)
            break
    for name in product_candidates:
        file_path = sample_path / name
        if file_path.exists():
            references["products"] = pd.read_csv(file_path, low_memory=False)
            break

    return references


def _cost_confidence(canonical: pd.DataFrame) -> dict[str, str | float]:
    if canonical.empty:
        return {
            "unit_cost_non_null_rate": 0.0,
            "unit_price_non_null_rate": 0.0,
            "unit_cost_confidence": "unavailable",
            "unit_price_confidence": "unavailable",
        }

    unit_cost_rate = float(canonical["unit_cost"].notna().mean()) if "unit_cost" in canonical.columns else 0.0
    unit_price_rate = float(canonical["unit_price"].notna().mean()) if "unit_price" in canonical.columns else 0.0

    def label(rate: float) -> str:
        if rate >= 0.95:
            return "measured"
        if rate >= 0.5:
            return "estimated"
        return "unavailable"

    return {
        "unit_cost_non_null_rate": unit_cost_rate,
        "unit_price_non_null_rate": unit_price_rate,
        "unit_cost_confidence": label(unit_cost_rate),
        "unit_price_confidence": label(unit_price_rate),
    }


def _to_markdown(
    contract_path: Path,
    sample_path: Path,
    rows_in: int,
    rows_out: int,
    required_fields_present: bool,
    report: dict,
    cost_confidence: dict[str, str | float],
) -> str:
    metrics = report["metrics"]
    failures = report["failures"]

    lines = [
        "# Customer Contract Validation",
        "",
        f"- Contract: `{contract_path}`",
        f"- Sample: `{sample_path}`",
        f"- Rows input: {rows_in}",
        f"- Rows mapped: {rows_out}",
        f"- Passed: `{report['passed']}`",
        f"- Canonical required fields present: `{required_fields_present}`",
        "",
        "## Metrics",
        "",
        "| metric | value | threshold |",
        "|---|---:|---:|",
        f"| date_parse_success | {metrics.get('date_parse_success', 0):.4f} | >= {report['thresholds']['min_date_parse_success']:.4f} |",
        f"| required_null_rate | {metrics.get('required_null_rate', 0):.4f} | <= {report['thresholds']['max_required_null_rate']:.4f} |",
        f"| duplicate_rate | {metrics.get('duplicate_rate', 0):.4f} | <= {report['thresholds']['max_duplicate_rate']:.4f} |",
        f"| quantity_parse_success | {metrics.get('quantity_parse_success', 0):.4f} | >= {report['thresholds']['min_quantity_parse_success']:.4f} |",
        "",
        "## Semantic DQ",
        "",
        f"- max_future_days_observed: {metrics.get('max_future_days_observed', 0):.2f}",
        f"- history_years_observed: {metrics.get('history_years_observed', 0):.2f}",
        f"- store_ref_missing_rate: {metrics.get('store_ref_missing_rate', 0):.4f}",
        f"- product_ref_missing_rate: {metrics.get('product_ref_missing_rate', 0):.4f}",
        "",
        "## Cost Field Confidence",
        "",
        f"- unit_cost_non_null_rate: {float(cost_confidence['unit_cost_non_null_rate']):.4f}",
        f"- unit_cost_confidence: `{cost_confidence['unit_cost_confidence']}`",
        f"- unit_price_non_null_rate: {float(cost_confidence['unit_price_non_null_rate']):.4f}",
        f"- unit_price_confidence: `{cost_confidence['unit_price_confidence']}`",
        "",
        "## Failures",
        "",
    ]

    if failures:
        lines.extend([f"- {failure}" for failure in failures])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Pass/fail thresholds are enforced from the contract profile dq_thresholds with strict defaults.",
            "- This validator gates onboarding before candidate retraining.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a tenant source contract against sample data")
    parser.add_argument("--contract", required=True, help="Path to YAML contract profile")
    parser.add_argument("--sample-path", required=True, help="Path to sample CSV/JSONL file or directory")
    parser.add_argument(
        "--output-json",
        default="backend/reports/contract_validation_report.json",
        help="Path to output JSON report",
    )
    parser.add_argument(
        "--output-md",
        default="backend/reports/contract_validation_report.md",
        help="Path to output Markdown report",
    )
    parser.add_argument(
        "--write-canonical",
        default=None,
        help="Optional path to write canonical mapped CSV",
    )
    args = parser.parse_args()

    contract_path = Path(args.contract).resolve()
    sample_path = Path(args.sample_path).resolve()

    try:
        profile = load_contract_profile(contract_path)
        raw_df = _load_sample(sample_path)
        reference_data = _load_reference_data(sample_path)
    except (ContractProfileError, FileNotFoundError, ValueError) as exc:
        print(f"Validation setup failed: {exc}")
        return 2

    result = build_canonical_result(raw_df, profile, reference_data=reference_data)
    canonical = result.dataframe
    report = result.report.to_dict()
    cost_confidence = _cost_confidence(canonical)

    required_fields_present = set(CANONICAL_REQUIRED_FIELDS).issubset(canonical.columns)

    payload = {
        "contract": str(contract_path),
        "sample_path": str(sample_path),
        "rows_input": int(len(raw_df)),
        "rows_mapped": int(len(canonical)),
        "required_fields_present": required_fields_present,
        "report": report,
        "cost_confidence": cost_confidence,
        "reference_data_loaded": sorted(reference_data.keys()),
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    markdown = _to_markdown(
        contract_path,
        sample_path,
        len(raw_df),
        len(canonical),
        required_fields_present,
        report,
        cost_confidence,
    )
    output_md.write_text(markdown, encoding="utf-8")

    if args.write_canonical:
        canonical_path = Path(args.write_canonical)
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        canonical.to_csv(canonical_path, index=False)

    print(markdown)
    return 0 if report["passed"] and required_fields_present else 2


if __name__ == "__main__":
    raise SystemExit(main())
