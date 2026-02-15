#!/usr/bin/env python3
"""
Benchmark in-domain forecasting baselines across canonical datasets.

Usage:
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py
  PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py --max-rows 150000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import xgboost as xgb

from ml.data_contracts import load_canonical_transactions
from ml.features import create_features, get_feature_cols
from ml.metrics_contract import compute_forecast_metrics

DATASET_DIRS = {
    "favorita": "data/kaggle/favorita",
    "walmart": "data/kaggle/walmart",
    "rossmann": "data/kaggle/rossmann",
}


def benchmark_dataset(dataset_id: str, data_dir: str, max_rows: int) -> dict:
    raw = load_canonical_transactions(data_dir)
    raw = raw.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    if len(raw) > max_rows:
        raw = raw.tail(max_rows).reset_index(drop=True)

    feat = create_features(raw, force_tier="cold_start")
    cols = [c for c in get_feature_cols("cold_start") if c in feat.columns]
    X = feat[cols].fillna(0)
    y = feat["quantity"].astype(float)

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    frequency = str(raw["frequency"].iloc[0]) if len(raw) else "unknown"

    params = {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "min_child_weight": 5,
        "random_state": 42,
    }
    model = xgb.XGBRegressor(**params)
    use_log_target = frequency == "weekly"
    if use_log_target:
        model.fit(X_train, np.log1p(y_train), verbose=False)
        preds = np.expm1(model.predict(X_test))
    else:
        model.fit(X_train, y_train, verbose=False)
        preds = model.predict(X_test)
    preds = np.maximum(preds, 0)
    metrics = compute_forecast_metrics(y_test, preds)

    return {
        "dataset_id": dataset_id,
        "rows_used": int(len(raw)),
        "rows_train": int(len(X_train)),
        "rows_test": int(len(X_test)),
        "frequency": frequency,
        "use_log_target": use_log_target,
        "mae": metrics["mae"],
        "mape_nonzero": metrics["mape_nonzero"],
        "mape": metrics["mape_nonzero"],  # Backward-compatible alias.
        "stockout_miss_rate": metrics["stockout_miss_rate"],
        "overstock_rate": metrics["overstock_rate"],
        "overstock_dollars": metrics["overstock_dollars"],
        "overstock_dollars_confidence": metrics["overstock_dollars_confidence"],
        "params": params,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark datasets with a fixed baseline model")
    parser.add_argument("--max-rows", type=int, default=200000, help="Max rows per dataset (tail sample)")
    parser.add_argument(
        "--output-json",
        type=str,
        default="backend/reports/dataset_benchmark_baseline.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    results = []
    for dataset_id, data_dir in DATASET_DIRS.items():
        result = benchmark_dataset(dataset_id, data_dir, args.max_rows)
        results.append(result)

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
