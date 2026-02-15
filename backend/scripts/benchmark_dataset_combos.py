#!/usr/bin/env python3
"""
Benchmark pairwise dataset combinations for demand forecasting.

Usage:
  PYTHONPATH=backend python3 backend/scripts/benchmark_dataset_combos.py
  PYTHONPATH=backend python3 backend/scripts/benchmark_dataset_combos.py --max-rows-each 120000
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.data_contracts import load_canonical_transactions
from ml.features import create_features, get_feature_cols
from ml.metrics_contract import compute_forecast_metrics

DATASET_DIRS = {
    "favorita": "data/kaggle/favorita",
    "walmart": "data/kaggle/walmart",
    "rossmann": "data/kaggle/rossmann",
}


def _calc_metrics(y_true: pd.Series, preds: np.ndarray) -> dict:
    preds = np.maximum(preds, 0)
    metrics = compute_forecast_metrics(y_true, preds)
    return {
        "mae": metrics["mae"],
        "mape_nonzero": metrics["mape_nonzero"],
        "mape": metrics["mape_nonzero"],  # Backward-compatible alias.
        "stockout_miss_rate": metrics["stockout_miss_rate"],
        "overstock_rate": metrics["overstock_rate"],
        "overstock_dollars": metrics["overstock_dollars"],
        "overstock_dollars_confidence": metrics["overstock_dollars_confidence"],
    }


def benchmark_combo(dataset_ids: tuple[str, str], max_rows_each: int) -> dict:
    parts = []
    frequencies = set()
    for ds in dataset_ids:
        raw = load_canonical_transactions(DATASET_DIRS[ds])
        raw = raw.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
        if len(raw) > max_rows_each:
            raw = raw.tail(max_rows_each).reset_index(drop=True)
        raw["source_dataset"] = ds
        frequencies.update(raw["frequency"].unique().tolist())
        parts.append(raw)

    combined = pd.concat(parts, ignore_index=True).sort_values(["date", "source_dataset"]).reset_index(drop=True)

    feat = create_features(combined, force_tier="cold_start")
    cols = [c for c in get_feature_cols("cold_start") if c in feat.columns]
    X = feat[cols].fillna(0)
    y = feat["quantity"].astype(float)
    source = feat["source_dataset"].astype(str)

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    src_test = source.iloc[split:]

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
    use_log_target = "weekly" in frequencies
    model = xgb.XGBRegressor(**params)
    if use_log_target:
        model.fit(X_train, np.log1p(y_train), verbose=False)
        preds = np.expm1(model.predict(X_test))
    else:
        model.fit(X_train, y_train, verbose=False)
        preds = model.predict(X_test)
    preds = np.maximum(preds, 0)

    overall = _calc_metrics(y_test, preds)
    per_dataset = {}
    for ds in dataset_ids:
        mask = src_test == ds
        if mask.sum() == 0:
            continue
        per_dataset[ds] = _calc_metrics(y_test[mask], preds[mask])
        per_dataset[ds]["rows_test"] = int(mask.sum())

    return {
        "combo_id": "+".join(dataset_ids),
        "dataset_ids": list(dataset_ids),
        "rows_used_total": int(len(combined)),
        "rows_train": int(len(X_train)),
        "rows_test": int(len(X_test)),
        "frequencies": sorted(list(frequencies)),
        "use_log_target": use_log_target,
        "overall": overall,
        "per_dataset_test": per_dataset,
        "params": params,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark pairwise dataset combinations")
    parser.add_argument("--max-rows-each", type=int, default=150000, help="Max rows per dataset in each combo")
    parser.add_argument(
        "--output-json",
        type=str,
        default="backend/reports/dataset_combo_benchmark.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    combos = list(itertools.combinations(DATASET_DIRS.keys(), 2))
    results = [benchmark_combo(c, args.max_rows_each) for c in combos]

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
