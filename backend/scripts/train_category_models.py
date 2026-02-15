#!/usr/bin/env python3
"""
Category Model Training — Train tier-specific demand forecast models.

Trains separate models for Fresh, General Merchandise, and Hardware
product tiers, then evaluates each against the global baseline.

Usage:
  python scripts/train_category_models.py
  python scripts/train_category_models.py --data-dir data/seed --promote
  python scripts/train_category_models.py --tiers fresh hardware
  python scripts/train_category_models.py --global-only  # retrain global baseline
  python scripts/train_category_models.py --tuned         # use tuned hyperparams

Iterations:
  1. Global baseline (default params)
  2. Tuned hyperparams (--tuned: n_estimators=750, max_depth=8)
  3. Category-specific models (per tier)
  4. Compare all → promote best per tier
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


TUNED_PARAMS = {
    "n_estimators": 750,
    "max_depth": 8,
    "learning_rate": 0.03,
    "subsample": 0.85,
    "colsample_bytree": 0.85,
    "reg_alpha": 0.05,
    "reg_lambda": 1.5,
    "min_child_weight": 3,
}


def main():
    parser = argparse.ArgumentParser(
        description="Train category-specific demand forecast models",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to CSV training data (default: auto-detect)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="seed",
        help="Dataset name for MLflow tracking",
    )
    parser.add_argument(
        "--tiers",
        nargs="*",
        default=None,
        help="Specific tiers to train (fresh, general_merchandise, hardware)",
    )
    parser.add_argument(
        "--global-only",
        action="store_true",
        help="Only retrain the global baseline model",
    )
    parser.add_argument(
        "--tuned",
        action="store_true",
        help="Use tuned hyperparameters instead of defaults",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Auto-promote models that beat the current champion",
    )
    args = parser.parse_args()

    from ml.features import create_features
    from ml.segmentation import ALL_TIERS, get_model_name, get_tier_categories
    from ml.train import save_models, train_ensemble, train_xgboost
    from workers.retrain import _load_csv_data, _next_version

    # ── Resolve data directory ────────────────────────────────────
    data_dir = args.data_dir
    if data_dir is None:
        for d in ["data/seed", "data/kaggle", "../data/seed"]:
            if os.path.isdir(d):
                data_dir = os.path.abspath(d)
                break
        if data_dir is None:
            print("No training data found. Run seed_enterprise_data.py first.")
            sys.exit(1)

    print("=" * 65)
    print("  ShelfOps Category Model Training Pipeline")
    print("=" * 65)
    print(f"  Data:    {data_dir}")
    print(f"  Dataset: {args.dataset}")
    print(f"  Tuned:   {args.tuned}")
    print(f"  Promote: {args.promote}")
    print()

    # ── Load all data ─────────────────────────────────────────────
    print("Loading training data...")
    transactions_df = _load_csv_data(data_dir)
    print(f"  Loaded {len(transactions_df):,} rows")
    print(f"  Stores: {transactions_df['store_id'].nunique()}")
    print(f"  Products: {transactions_df['product_id'].nunique()}")

    if "category" not in transactions_df.columns:
        print("\n  WARNING: No 'category' column found. Cannot train tier models.")
        print("  Falling back to global-only training.")
        args.global_only = True

    results = []
    total_start = time.time()

    # ── Global Baseline ───────────────────────────────────────────
    print("\n" + "-" * 65)
    print("  Training Global Baseline")
    print("-" * 65)

    version = _next_version()
    features_df = create_features(transactions_df=transactions_df)
    suffix = "_tuned" if args.tuned else ""
    global_model_name = f"demand_forecast{suffix}"

    start = time.time()
    ensemble_result = train_ensemble(
        features_df=features_df,
        dataset_name=args.dataset,
        version=version,
        model_name=global_model_name,
    )
    elapsed = time.time() - start

    xgb_mae = ensemble_result["xgboost"]["metrics"].get("mae", 0)
    xgb_mape = ensemble_result["xgboost"]["metrics"].get("mape", 0)
    ensemble_mae = ensemble_result["ensemble"].get("estimated_mae", 0)

    save_models(
        ensemble_result=ensemble_result,
        version=version,
        dataset_name=args.dataset,
        promote=args.promote,
    )

    results.append(
        {
            "model": global_model_name,
            "version": version,
            "rows": len(features_df),
            "xgb_mae": round(xgb_mae, 4),
            "xgb_mape": round(xgb_mape, 4),
            "ensemble_mae": round(ensemble_mae, 4),
            "time_sec": round(elapsed, 1),
        }
    )

    print(f"  Version:      {version}")
    print(f"  XGBoost MAE:  {xgb_mae:.4f}")
    print(f"  XGBoost MAPE: {xgb_mape:.4f}")
    print(f"  Ensemble MAE: {ensemble_mae:.4f}")
    print(f"  Time:         {elapsed:.1f}s")

    if args.global_only:
        _print_summary(results, time.time() - total_start)
        return 0

    # ── Category-Specific Models ──────────────────────────────────
    tiers_to_train = args.tiers or ALL_TIERS

    for tier in tiers_to_train:
        categories = get_tier_categories(tier)
        tier_model_name = get_model_name(tier)

        print(f"\n{'-' * 65}")
        print(f"  Training: {tier_model_name}")
        print(f"  Categories: {', '.join(categories)}")
        print(f"{'-' * 65}")

        # Filter transactions by category
        tier_txn = transactions_df[transactions_df["category"].isin(categories)]

        if len(tier_txn) < 1000:
            print(f"  SKIPPED — only {len(tier_txn)} rows (need 1000+)")
            continue

        tier_features = create_features(transactions_df=tier_txn)
        tier_version = _next_version()

        start = time.time()
        tier_result = train_ensemble(
            features_df=tier_features,
            dataset_name=f"{args.dataset}_{tier}",
            version=tier_version,
            model_name=tier_model_name,
        )
        elapsed = time.time() - start

        tier_xgb_mae = tier_result["xgboost"]["metrics"].get("mae", 0)
        tier_xgb_mape = tier_result["xgboost"]["metrics"].get("mape", 0)
        tier_ensemble_mae = tier_result["ensemble"].get("estimated_mae", 0)

        # Promote if it beats global baseline for this tier's data
        should_promote = args.promote and tier_xgb_mae < xgb_mae

        save_models(
            ensemble_result=tier_result,
            version=tier_version,
            dataset_name=f"{args.dataset}_{tier}",
            promote=should_promote,
        )

        results.append(
            {
                "model": tier_model_name,
                "version": tier_version,
                "rows": len(tier_features),
                "xgb_mae": round(tier_xgb_mae, 4),
                "xgb_mape": round(tier_xgb_mape, 4),
                "ensemble_mae": round(tier_ensemble_mae, 4),
                "time_sec": round(elapsed, 1),
                "vs_global": f"{((tier_xgb_mae - xgb_mae) / xgb_mae * 100):+.1f}%",
                "promoted": should_promote,
            }
        )

        print(f"  Version:      {tier_version}")
        print(f"  Rows:         {len(tier_features):,}")
        print(f"  XGBoost MAE:  {tier_xgb_mae:.4f}")
        print(f"  XGBoost MAPE: {tier_xgb_mape:.4f}")
        print(f"  vs Global:    {((tier_xgb_mae - xgb_mae) / xgb_mae * 100):+.1f}%")
        print(f"  Promoted:     {should_promote}")
        print(f"  Time:         {elapsed:.1f}s")

    _print_summary(results, time.time() - total_start)
    return 0


def _print_summary(results: list[dict], total_time: float) -> None:
    """Print training results summary table."""
    print("\n" + "=" * 65)
    print("  Training Results Summary")
    print("=" * 65)
    print(f"  {'Model':<30} {'Version':<8} {'MAE':<10} {'MAPE':<10} {'vs Global':<10}")
    print(f"  {'-' * 30} {'-' * 8} {'-' * 10} {'-' * 10} {'-' * 10}")

    for r in results:
        vs = r.get("vs_global", "baseline")
        promoted = " *" if r.get("promoted") else ""
        print(f"  {r['model']:<30} {r['version']:<8} {r['xgb_mae']:<10.4f} {r['xgb_mape']:<10.4f} {vs:<10}{promoted}")

    print(f"\n  Total time: {total_time:.1f}s")
    print("  * = promoted to champion")
    print()


if __name__ == "__main__":
    sys.exit(main())
