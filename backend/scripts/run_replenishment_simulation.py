#!/usr/bin/env python3
from __future__ import annotations

import argparse

from ml.replenishment_simulation import (
    DEFAULT_DATA_DIR,
    DEFAULT_OUTPUT_JSON,
    DEFAULT_OUTPUT_MD,
    SimulationConfig,
    run_replenishment_simulation,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run replenishment replay simulation on benchmark data")
    parser.add_argument("--data-dir", type=str, default=DEFAULT_DATA_DIR, help="Directory with canonical benchmark transactions")
    parser.add_argument("--dataset-id", type=str, default="m5_walmart", help="Dataset id label for the report")
    parser.add_argument("--replay-days", type=int, default=28, help="Number of trailing replay days")
    parser.add_argument("--warmup-days", type=int, default=56, help="Minimum history days before replay")
    parser.add_argument("--max-series", type=int, default=50, help="Max store-product series to replay")
    parser.add_argument("--lead-time-days", type=int, default=5, help="Simulated lead time")
    parser.add_argument("--output-json", type=str, default=DEFAULT_OUTPUT_JSON, help="Output JSON report path")
    parser.add_argument("--output-md", type=str, default=DEFAULT_OUTPUT_MD, help="Output Markdown report path")
    args = parser.parse_args()

    config = SimulationConfig(
        dataset_id=args.dataset_id,
        replay_days=args.replay_days,
        warmup_days=args.warmup_days,
        max_series=args.max_series,
        lead_time_days=args.lead_time_days,
    )
    run_replenishment_simulation(
        data_dir=args.data_dir,
        config=config,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
