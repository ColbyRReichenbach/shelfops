#!/usr/bin/env python3
"""
Standalone Training Script — Run the ML pipeline from the command line.

Usage:
  python scripts/run_training.py --data-dir data/seed --version v1
  python scripts/run_training.py --data-dir data/kaggle --dataset favorita --promote
  python scripts/run_training.py --help

This is the recommended way to run your first training before
Celery workers are operational.
"""

import argparse
import os
import sys
import time

# Add backend to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser(
        description="ShelfOps ML Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train on synthetic seed data
  python scripts/run_training.py --data-dir data/seed --version v1

  # Train on Kaggle Favorita data
  python scripts/run_training.py --data-dir data/kaggle --dataset favorita --promote

  # Auto-detect version and data
  python scripts/run_training.py
        """,
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Path to CSV training data directory (default: auto-detect)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="unknown",
        help="Dataset name for MLflow tracking (default: unknown)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Model version string, e.g. v1 (default: auto-increment)",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote this version to champion after training",
    )
    parser.add_argument(
        "--tier",
        choices=["cold_start", "production"],
        default=None,
        help="Force feature tier (default: auto-detect)",
    )

    args = parser.parse_args()

    # ── Import ML modules ────────────────────────────────────────────
    try:
        import structlog

        logger = structlog.get_logger()
    except ImportError:
        import logging

        logger = logging.getLogger(__name__)  # noqa: F841
        logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  ShelfOps ML Training Pipeline")
    print("=" * 60)

    # ── Resolve data directory ───────────────────────────────────────
    data_dir = args.data_dir
    if data_dir is None:
        # Auto-detect: check common locations
        candidates = [
            os.path.join(os.getcwd(), "data", "seed"),
            os.path.join(os.getcwd(), "data", "kaggle"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "seed"),
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "kaggle"),
        ]
        for d in candidates:
            d = os.path.abspath(d)
            if os.path.isdir(d) and any(f.endswith(".csv") for f in os.listdir(d)):
                data_dir = d
                print(f"  Auto-detected data: {d}")
                break

        if data_dir is None:
            print("\n❌ No training data found.")
            print("   Run one of these first:")
            print("     python scripts/seed_enterprise_data.py --output data/seed")
            print("     python scripts/download_kaggle_data.py --output data/kaggle")
            sys.exit(1)

    if not os.path.isdir(data_dir):
        print(f"\n❌ Data directory not found: {data_dir}")
        sys.exit(1)

    # ── Load and prepare data ────────────────────────────────────────
    from ml.features import create_features
    from ml.train import save_models, train_ensemble
    from workers.retrain import _load_csv_data, _next_version

    version = args.version or _next_version()

    print(f"\n  Data dir:  {data_dir}")
    print(f"  Dataset:   {args.dataset}")
    print(f"  Version:   {version}")
    print(f"  Promote:   {args.promote}")
    print(f"  Tier:      {args.tier or 'auto-detect'}")
    print()

    start = time.time()

    # Step 1: Load data
    print("Step 1/4: Loading training data...")
    transactions_df = _load_csv_data(data_dir)
    print(
        f"  ✓ Loaded {len(transactions_df):,} rows "
        f"({transactions_df['store_id'].nunique()} stores, "
        f"{transactions_df['product_id'].nunique()} products)"
    )

    # Step 2: Feature engineering
    print("\nStep 2/4: Engineering features...")
    features_df = create_features(
        transactions_df=transactions_df,
        force_tier=args.tier,
    )
    tier = getattr(features_df, "_feature_tier", "unknown")
    print(f"  ✓ Created {len(features_df.columns)} features ({tier} tier)")
    print(f"  ✓ {len(features_df):,} training rows")

    # Step 3: Train ensemble
    print("\nStep 3/4: Training XGBoost + LSTM ensemble...")
    ensemble_result = train_ensemble(
        features_df=features_df,
        dataset_name=args.dataset,
        version=version,
    )

    xgb_metrics = ensemble_result.get("xgboost", {}).get("metrics", {})
    lstm_metrics = ensemble_result.get("lstm", {}).get("metrics", {})
    ensemble_info = ensemble_result.get("ensemble", {})

    print(f"  ✓ XGBoost MAE:  {xgb_metrics.get('mae', 'N/A')}")
    print(f"  ✓ LSTM MAE:     {lstm_metrics.get('mae', 'N/A')}")
    print(f"  ✓ Ensemble MAE: {ensemble_info.get('estimated_mae', 'N/A')}")
    print(f"  ✓ XGBoost MAPE: {xgb_metrics.get('mape', 'N/A')}")

    # Step 4: Save + register
    print("\nStep 4/4: Saving models and registering...")
    save_models(
        ensemble_result=ensemble_result,
        version=version,
        dataset_name=args.dataset,
        promote=args.promote,
    )

    elapsed = time.time() - start
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models", version)
    model_dir = os.path.abspath(model_dir)

    print("\n" + "=" * 60)
    print("  ✅ Training Complete!")
    print("=" * 60)
    print(f"  Version:   {version}")
    print(f"  Tier:      {tier}")
    print(f"  MAE:       {ensemble_info.get('estimated_mae', 'N/A')}")
    print(f"  MAPE:      {xgb_metrics.get('mape', 'N/A')}")
    print(f"  Promoted:  {args.promote}")
    print(f"  Time:      {elapsed:.1f}s")
    print(f"  Artifacts: {model_dir}")
    print()

    # List saved artifacts
    if os.path.isdir(model_dir):
        print("  Saved files:")
        for f in sorted(os.listdir(model_dir)):
            size = os.path.getsize(os.path.join(model_dir, f))
            print(f"    {f} ({size:,} bytes)")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
