"""
ML Retraining Workers — Scheduled model retraining.

Runs the full ML pipeline:
  1. Load training data (CSV cold-start or DB query)
  2. Feature engineering (auto-detects tier)
  3. Train XGBoost + LSTM ensemble
  4. Save models + register in model registry
  5. Refresh alerts with updated forecasts
"""

import os
import glob
import json
from datetime import datetime, timezone

import pandas as pd
import structlog

from workers.celery_app import celery_app

logger = structlog.get_logger()


def _next_version() -> str:
    """Auto-increment model version by scanning existing model directories."""
    from ml.train import MODEL_DIR

    existing = glob.glob(os.path.join(MODEL_DIR, "v*"))
    if not existing:
        return "v1"
    versions = []
    for d in existing:
        name = os.path.basename(d)
        if name.startswith("v") and name[1:].isdigit():
            versions.append(int(name[1:]))
    return f"v{max(versions) + 1}" if versions else "v1"


def _load_csv_data(data_dir: str) -> pd.DataFrame:
    """
    Load training data from CSV files in a directory.

    Supports Kaggle datasets (Favorita, Walmart, Rossmann) and
    synthetic seed data. Returns a unified DataFrame with columns:
    (store_id, product_id, date, quantity, category).
    """
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for f in csv_files:
        df = pd.read_csv(f, parse_dates=["date"] if "date" in pd.read_csv(f, nrows=0).columns else False)
        frames.append(df)
        logger.info("retrain.loaded_csv", file=os.path.basename(f), rows=len(df))

    combined = pd.concat(frames, ignore_index=True)

    # Normalize column names for common Kaggle datasets
    rename_map = {}
    cols_lower = {c.lower(): c for c in combined.columns}

    # Favorita: store_nbr → store_id, family → category, sales → quantity
    if "store_nbr" in cols_lower:
        rename_map[cols_lower["store_nbr"]] = "store_id"
    if "family" in cols_lower and "category" not in cols_lower:
        rename_map[cols_lower["family"]] = "category"
    if "sales" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["sales"]] = "quantity"
    # Walmart: Store → store_id, Dept → category, Weekly_Sales → quantity
    if "store" in cols_lower and "store_id" not in cols_lower:
        rename_map[cols_lower["store"]] = "store_id"
    if "dept" in cols_lower and "category" not in cols_lower:
        rename_map[cols_lower["dept"]] = "category"
    if "weekly_sales" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["weekly_sales"]] = "quantity"
    # Rossmann: Store → store_id, Sales → quantity
    if "sales" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["sales"]] = "quantity"

    if rename_map:
        combined = combined.rename(columns=rename_map)
        logger.info("retrain.normalized_columns", remapped=list(rename_map.keys()))

    # Ensure required columns
    required = {"store_id", "date", "quantity"}
    missing = required - set(combined.columns)
    if missing:
        raise ValueError(f"Missing required columns after normalization: {missing}")

    # Add product_id if missing (aggregate by store + category)
    if "product_id" not in combined.columns:
        if "category" in combined.columns:
            combined["product_id"] = combined["category"].astype(str)
        elif "item_nbr" in combined.columns:
            combined["product_id"] = combined["item_nbr"].astype(str)
        else:
            combined["product_id"] = "all"

    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(combined["date"]):
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
        combined = combined.dropna(subset=["date"])

    # Cast store_id and product_id to strings
    combined["store_id"] = combined["store_id"].astype(str)
    combined["product_id"] = combined["product_id"].astype(str)

    logger.info(
        "retrain.data_ready",
        rows=len(combined),
        stores=combined["store_id"].nunique(),
        products=combined["product_id"].nunique(),
        date_range=f"{combined['date'].min()} → {combined['date'].max()}",
    )

    return combined


@celery_app.task(
    name="workers.retrain.retrain_forecast_model",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
)
def retrain_forecast_model(
    self,
    customer_id: str | None = None,
    data_dir: str | None = None,
    version: str | None = None,
    dataset_name: str = "unknown",
    promote: bool = False,
):
    """
    Retrain demand forecast model.

    Modes:
      - Cold-start: Pass data_dir pointing to CSV files (Kaggle/synthetic)
      - Production: Pass customer_id to query DB (future — requires async DB)

    Args:
        customer_id: Tenant ID for DB-sourced data (future)
        data_dir: Path to CSV training data directory
        version: Model version string (auto-incremented if None)
        dataset_name: Name for MLflow tracking (e.g., "favorita")
        promote: If True, promote this version to champion
    """
    from ml.features import create_features
    from ml.train import train_ensemble, save_models

    run_id = self.request.id or "manual"
    ver = version or _next_version()

    logger.info(
        "retrain.started",
        run_id=run_id,
        customer_id=customer_id,
        data_dir=data_dir,
        version=ver,
        dataset_name=dataset_name,
    )

    try:
        # ── Step 1: Load data ────────────────────────────────────────
        if data_dir:
            transactions_df = _load_csv_data(data_dir)
        else:
            # TODO: Production mode — query DB for customer's transaction data
            # For now, try default seed data location
            default_dirs = ["data/seed", "data/kaggle", "../data/seed"]
            transactions_df = None
            for d in default_dirs:
                if os.path.isdir(d):
                    transactions_df = _load_csv_data(d)
                    dataset_name = os.path.basename(d)
                    break
            if transactions_df is None:
                raise FileNotFoundError(
                    "No data_dir specified and no default data found. "
                    "Run seed_enterprise_data.py or download_kaggle_data.py first."
                )

        # ── Step 2: Feature engineering ──────────────────────────────
        logger.info("retrain.creating_features", rows=len(transactions_df))
        features_df = create_features(
            transactions_df=transactions_df,
            force_tier="cold_start" if data_dir else None,
        )
        logger.info(
            "retrain.features_created",
            rows=len(features_df),
            columns=len(features_df.columns),
            tier=getattr(features_df, "_feature_tier", "unknown"),
        )

        # ── Step 3: Train ensemble ───────────────────────────────────
        logger.info("retrain.training", version=ver, dataset=dataset_name)
        ensemble_result = train_ensemble(
            features_df=features_df,
            dataset_name=dataset_name,
            version=ver,
        )

        metrics = ensemble_result.get("metrics", {})
        logger.info(
            "retrain.trained",
            version=ver,
            tier=ensemble_result.get("tier", "unknown"),
            mae=metrics.get("ensemble_mae"),
            mape=metrics.get("ensemble_mape"),
        )

        # ── Step 4: Save models + register ───────────────────────────
        save_models(
            ensemble_result=ensemble_result,
            version=ver,
            dataset_name=dataset_name,
            promote=promote,
        )
        logger.info("retrain.saved", version=ver, promoted=promote)

        # ── Step 5: Summary ──────────────────────────────────────────
        summary = {
            "status": "success",
            "version": ver,
            "dataset": dataset_name,
            "tier": ensemble_result.get("tier", "unknown"),
            "rows_trained": len(features_df),
            "mae": metrics.get("ensemble_mae"),
            "mape": metrics.get("ensemble_mape"),
            "promoted": promote,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("retrain.completed", **summary)
        return summary

    except Exception as exc:
        logger.error(
            "retrain.failed",
            run_id=run_id,
            version=ver,
            error=str(exc),
            exc_info=True,
        )
        # Retry on transient errors (not data errors)
        if isinstance(exc, (OSError, IOError)):
            raise self.retry(exc=exc)
        raise
