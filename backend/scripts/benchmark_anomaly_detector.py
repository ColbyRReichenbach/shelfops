#!/usr/bin/env python3
"""Generate FreshRetailNet stockout/anomaly detector benchmark evidence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.anomaly_benchmark import build_stockout_anomaly_report

DEFAULT_DATA_DIR = "data/benchmarks/freshretailnet_50k/raw"
DEFAULT_OUTPUT_JSON = "backend/reports/freshretailnet_anomaly_benchmark.json"
DEFAULT_OUTPUT_MD = "backend/reports/freshretailnet_anomaly_benchmark.md"


def render_markdown(report: dict) -> str:
    lines = [
        "# FreshRetailNet Anomaly Detector Benchmark",
        "",
        f"- dataset_id: `{report['dataset_id']}`",
        f"- model_family: `{report['model_family']}`",
        f"- task: `{report['task']}`",
        f"- rows_eval: `{report['rows_eval']}`",
        f"- date_min: `{report['date_min']}`",
        f"- date_max: `{report['date_max']}`",
        f"- positive_rate: `{report['positive_rate']}`",
        f"- feature_set_id: `{report['feature_set_id']}`",
        f"- evaluation_protocol: {report['evaluation_protocol']}",
        f"- claim_boundary: {report['claim_boundary']}",
        "",
        "| profile | stage | threshold | precision | recall | f1 | false_positive_rate | review_rate |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['model_name']} | {row['status']} | {row['threshold']:.2f} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | "
            f"{row['false_positive_rate']:.4f} | {row['review_rate']:.4f} |"
        )

    decision = report.get("promotion_decision") or {}
    lines.extend(
        [
            "",
            "## Promotion Decision",
            "",
            f"- decision: `{decision.get('decision', 'unavailable')}`",
            f"- reason: {decision.get('reason', 'unavailable')}",
            "",
            "This report evaluates stockout/inventory-integrity detection only. It does not prove measured merchant ROI.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark anomaly detector profiles on FreshRetailNet")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--max-rows", type=int, default=250_000)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()

    report = build_stockout_anomaly_report(args.data_dir, max_rows=args.max_rows)

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
