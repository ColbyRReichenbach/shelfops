#!/usr/bin/env python3
"""Run a lightweight ensemble-vs-single strategy cycle and emit evidence artifacts."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml.data_contracts import load_canonical_transactions
from ml.features import create_features, get_feature_cols
from ml.train import train_lstm, train_xgboost


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.inf


def main() -> int:
    parser = argparse.ArgumentParser(description="Run model strategy cycle (single vs ensemble heuristic sweep)")
    parser.add_argument("--data-dir", default="data/seed", help="Canonical source directory")
    parser.add_argument("--max-rows", type=int, default=25000, help="Max rows to use")
    parser.add_argument("--output-json", default="docs/productization_artifacts/model_strategy_cycle.json")
    parser.add_argument("--output-md", default="docs/productization_artifacts/model_strategy_cycle.md")
    args = parser.parse_args()

    transactions = load_canonical_transactions(args.data_dir).sort_values(["date", "store_id", "product_id"])
    if args.max_rows > 0 and len(transactions) > args.max_rows:
        transactions = transactions.tail(args.max_rows).reset_index(drop=True)

    features = create_features(transactions_df=transactions, force_tier="cold_start")
    feature_cols = [c for c in get_feature_cols("cold_start") if c in features.columns]

    xgb_model, xgb_metrics = train_xgboost(
        features,
        feature_cols=feature_cols,
        params={
            "n_estimators": 250,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "early_stopping_rounds": 20,
            "random_state": 42,
        },
    )
    _ = xgb_model  # kept for explicit run parity

    lstm_available = True
    try:
        _, lstm_metrics = train_lstm(
            features,
            feature_cols=feature_cols,
            sequence_length=14,
            epochs=5,
            batch_size=64,
            max_samples=min(12000, len(features)),
        )
    except Exception as exc:  # noqa: BLE001
        lstm_available = False
        lstm_metrics = {"mae": math.inf, "mape": math.inf, "error": str(exc)}

    xgb_mae = _to_float(xgb_metrics.get("mae"))
    lstm_mae = _to_float(lstm_metrics.get("mae"))
    xgb_mape = _to_float(xgb_metrics.get("mape"))
    lstm_mape = _to_float(lstm_metrics.get("mape"))

    weight_candidates = [1.0, 0.9, 0.8, 0.7, 0.65, 0.6, 0.5]
    sweep = []
    for xgb_weight in weight_candidates:
        lstm_weight = round(1.0 - xgb_weight, 2)
        if lstm_available and math.isfinite(lstm_mae):
            est_mae = xgb_weight * xgb_mae + lstm_weight * lstm_mae
            est_mape = xgb_weight * xgb_mape + lstm_weight * lstm_mape
        else:
            est_mae = xgb_mae
            est_mape = xgb_mape
        sweep.append(
            {
                "xgboost_weight": xgb_weight,
                "lstm_weight": lstm_weight,
                "estimated_mae": round(est_mae, 6),
                "estimated_mape": round(est_mape, 6),
            }
        )

    best = min(sweep, key=lambda row: row["estimated_mae"])
    recommended_mode = "single_xgboost" if best["xgboost_weight"] >= 0.99 else "ensemble"

    decision = {
        "recommended_mode": recommended_mode,
        "recommended_weights": {
            "xgboost": best["xgboost_weight"],
            "lstm": best["lstm_weight"],
        },
        "promotion_status": "hold_as_challenger",
        "promotion_reason": "business_metrics_not_available_in_this_cycle",
    }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": args.data_dir,
        "rows_used": int(len(features)),
        "feature_count": len(feature_cols),
        "xgboost_metrics": {
            "mae": round(xgb_mae, 6),
            "mape": round(xgb_mape, 6),
        },
        "lstm_metrics": {
            "available": lstm_available,
            "mae": None if not math.isfinite(lstm_mae) else round(lstm_mae, 6),
            "mape": None if not math.isfinite(lstm_mape) else round(lstm_mape, 6),
            "error": lstm_metrics.get("error"),
        },
        "weight_sweep": sweep,
        "decision": decision,
    }

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Model Strategy Cycle",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- data_dir: `{payload['data_dir']}`",
        f"- rows_used: `{payload['rows_used']}`",
        f"- feature_count: `{payload['feature_count']}`",
        "",
        "## Base Metrics",
        "",
        f"- xgboost_mae: `{payload['xgboost_metrics']['mae']}`",
        f"- xgboost_mape: `{payload['xgboost_metrics']['mape']}`",
        f"- lstm_available: `{payload['lstm_metrics']['available']}`",
        f"- lstm_mae: `{payload['lstm_metrics']['mae']}`",
        f"- lstm_mape: `{payload['lstm_metrics']['mape']}`",
        "",
        "## Weight Sweep",
        "",
        "| xgboost_weight | lstm_weight | estimated_mae | estimated_mape |",
        "|---:|---:|---:|---:|",
    ]
    for row in sweep:
        lines.append(
            f"| {row['xgboost_weight']:.2f} | {row['lstm_weight']:.2f} | "
            f"{row['estimated_mae']:.6f} | {row['estimated_mape']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- recommended_mode: `{decision['recommended_mode']}`",
            f"- recommended_weights: xgboost={decision['recommended_weights']['xgboost']}, "
            f"lstm={decision['recommended_weights']['lstm']}",
            f"- promotion_status: `{decision['promotion_status']}`",
            f"- promotion_reason: `{decision['promotion_reason']}`",
        ]
    )
    Path(args.output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
