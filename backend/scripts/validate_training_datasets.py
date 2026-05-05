#!/usr/bin/env python3
"""
Validate and summarize training dataset readiness for multi-domain modeling.

Usage:
  python backend/scripts/validate_training_datasets.py
  python backend/scripts/validate_training_datasets.py --base-dir . --output backend/reports/DATASET_VALIDATION_REPORT.md
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ml.data_contracts import CANONICAL_REQUIRED_COLS, inspect_dataset_readiness, load_canonical_transactions


@dataclass
class DatasetResult:
    dataset_key: str
    data_dir: Path
    status: str
    message: str
    rows: int = 0
    stores: int = 0
    products: int = 0
    date_min: str = ""
    date_max: str = ""
    frequency: str = ""
    country_code: str = ""
    forecast_grain: str = ""
    missing_required: list[str] | None = None


DATASET_PATHS = {
    "m5_walmart": "data/benchmarks/m5_walmart",
    "freshretailnet_50k": "data/benchmarks/freshretailnet_50k",
    "csv_onboarding": "data/onboarding/csv",
    "square_exports": "data/onboarding/square",
    "favorita_legacy": "data/kaggle/favorita",
}


def validate_dataset(dataset_key: str, data_dir: Path) -> DatasetResult:
    if not data_dir.exists():
        return DatasetResult(
            dataset_key=dataset_key,
            data_dir=data_dir,
            status="missing",
            message="Directory not found",
        )

    readiness = inspect_dataset_readiness(data_dir)
    if readiness.status in {"blocked", "invalid"}:
        return DatasetResult(
            dataset_key=dataset_key,
            data_dir=data_dir,
            status=readiness.status,
            message=readiness.message,
            rows=readiness.row_count,
            date_min=readiness.date_min,
            date_max=readiness.date_max,
            forecast_grain=readiness.forecast_grain,
            missing_required=sorted(set(readiness.missing_files + readiness.missing_fields)),
        )

    try:
        df = load_canonical_transactions(str(data_dir))
    except Exception as exc:  # noqa: BLE001 - explicit report path
        return DatasetResult(
            dataset_key=dataset_key,
            data_dir=data_dir,
            status="error",
            message=str(exc),
        )

    missing = sorted(list(CANONICAL_REQUIRED_COLS - set(df.columns)))
    if missing:
        return DatasetResult(
            dataset_key=dataset_key,
            data_dir=data_dir,
            status="invalid",
            message="Missing canonical required fields after normalization",
            missing_required=missing,
        )

    return DatasetResult(
        dataset_key=dataset_key,
        data_dir=data_dir,
        status="ready",
        message="Canonical contract valid",
        rows=len(df),
        stores=df["store_id"].nunique(),
        products=df["product_id"].nunique(),
        date_min=str(pd.to_datetime(df["date"]).min().date()) if len(df) else "",
        date_max=str(pd.to_datetime(df["date"]).max().date()) if len(df) else "",
        frequency=str(df["frequency"].iloc[0]) if len(df) else "",
        country_code=str(df["country_code"].iloc[0]) if len(df) else "",
        forecast_grain=readiness.forecast_grain,
    )


def render_markdown(results: list[DatasetResult], base_dir: Path | None = None) -> str:
    lines = [
        "# Training Dataset Validation Report",
        "",
        "| dataset | path | status | rows | stores | products | date_min | date_max | frequency | country | grain | notes |",
        "|---|---|---|---:|---:|---:|---|---|---|---|---|---|",
    ]

    for r in results:
        notes = r.message
        if r.missing_required:
            notes += f"; missing_required={','.join(r.missing_required)}"
        path_display = str(r.data_dir)
        if base_dir is not None:
            try:
                path_display = str(r.data_dir.relative_to(base_dir))
            except ValueError:
                path_display = str(r.data_dir)
        lines.append(
            f"| {r.dataset_key} | `{path_display}` | `{r.status}` | {r.rows} | {r.stores} | {r.products} | "
            f"{r.date_min or '-'} | {r.date_max or '-'} | {r.frequency or '-'} | {r.country_code or '-'} | "
            f"{r.forecast_grain or '-'} | {notes} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `ready`: canonical contract loads and required fields are present.",
            "- `missing`: dataset directory is not present locally.",
            "- `error`: loader failed after readiness checks.",
            "- `blocked`: legacy Favorita-style layout is present but missing required source files or fields.",
            "- Active target scope is M5 + FreshRetailNet + CSV/Square; Favorita is legacy/reference only.",
            "- Public datasets are training/evaluation domains only and do not populate live tenant catalogs.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate multi-dataset training readiness")
    parser.add_argument("--base-dir", type=str, default=".", help="Project root (default: current directory)")
    parser.add_argument(
        "--output",
        type=str,
        default="backend/reports/DATASET_VALIDATION_REPORT.md",
        help="Output markdown report path (default: backend/reports/DATASET_VALIDATION_REPORT.md)",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    results = []
    for key, rel_path in DATASET_PATHS.items():
        results.append(validate_dataset(key, base_dir / rel_path))

    report = render_markdown(results, base_dir=base_dir)
    output_path = base_dir / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
