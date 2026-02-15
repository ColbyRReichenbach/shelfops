#!/usr/bin/env python3
"""
Compare Walmart target transforms for weekly net sales handling.

Outputs a JSON report with baseline metrics for:
  - legacy_abs_transform
  - clipped_target_with_return_signal
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

from ml.features import create_features, get_feature_cols
from ml.metrics_contract import compute_forecast_metrics


def _evaluate(df: pd.DataFrame) -> dict:
    feat = create_features(df, force_tier="cold_start")
    cols = [c for c in get_feature_cols("cold_start") if c in feat.columns]
    X = feat[cols].fillna(0)
    y = feat["quantity"].astype(float)

    split = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.1,
        reg_lambda=1.0,
        min_child_weight=5,
        random_state=42,
    )
    model.fit(X_train, np.log1p(y_train), verbose=False)
    preds = np.expm1(model.predict(X_test))
    return compute_forecast_metrics(y_test, preds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Walmart transform sensitivity benchmark")
    parser.add_argument("--data-dir", default="data/kaggle/walmart", help="Path containing Walmart train.csv")
    parser.add_argument(
        "--output",
        default="backend/reports/walmart_transform_sensitivity.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    train_path = Path(args.data_dir) / "train.csv"
    train = pd.read_csv(train_path, parse_dates=["Date"], low_memory=False)

    base = train.rename(
        columns={
            "Store": "store_id",
            "Dept": "category",
            "Date": "date",
            "IsHoliday": "is_holiday",
        }
    )
    base["store_id"] = base["store_id"].astype(str)
    base["category"] = base["category"].astype(str)
    base["product_id"] = base["category"]
    base["is_promotional"] = 0
    net_sales = pd.to_numeric(train["Weekly_Sales"], errors="coerce").fillna(0.0)

    clip_df = base.copy()
    clip_df["quantity"] = net_sales.clip(lower=0.0)
    clip_df["returns_adjustment"] = net_sales.clip(upper=0.0)
    clip_df["is_return_week"] = (net_sales < 0).astype(int)

    abs_df = base.copy()
    abs_df["quantity"] = net_sales.abs()
    abs_df["returns_adjustment"] = 0.0
    abs_df["is_return_week"] = 0

    report = {
        "dataset": "walmart",
        "rows": int(len(train)),
        "negative_week_share": float((net_sales < 0).mean()),
        "transforms": {
            "legacy_abs_transform": _evaluate(abs_df),
            "clipped_target_with_return_signal": _evaluate(clip_df),
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
