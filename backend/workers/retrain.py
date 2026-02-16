"""
ML Retraining Workers — Scheduled model retraining.

Runs the full ML pipeline:
  1. Load training data (CSV cold-start or DB query)
  2. Feature engineering (auto-detects tier)
  3. Train XGBoost model (default) with optional LSTM ensemble
  4. Save models + register in model registry
  5. Refresh alerts with updated forecasts
"""

import glob
import json
import os
from datetime import datetime, timezone

import pandas as pd
import structlog

from core.config import get_settings
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
    # Recursively scan directory so callers can point at data/seed root.
    csv_files = sorted(glob.glob(os.path.join(data_dir, "**", "*.csv"), recursive=True))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    date_aliases = ("date", "trans_date", "transaction_date")
    qty_aliases = ("quantity", "qty_sold", "quantity_sold", "sales", "weekly_sales")
    store_aliases = ("store_id", "store_nbr", "store", "store_code")
    skipped_files = 0
    skipped_examples: list[str] = []

    for f in csv_files:
        header_cols = pd.read_csv(f, nrows=0).columns.tolist()
        cols_lower = {c.lower(): c for c in header_cols}

        has_date = any(alias in cols_lower for alias in date_aliases)
        has_qty = any(alias in cols_lower for alias in qty_aliases)
        has_store = any(alias in cols_lower for alias in store_aliases)

        # Skip non-transaction files (e.g., product/store master, inventory snapshots).
        if not (has_date and has_qty and has_store):
            skipped_files += 1
            if len(skipped_examples) < 5:
                skipped_examples.append(os.path.basename(f))
            continue

        parse_date_col = next((cols_lower[a] for a in date_aliases if a in cols_lower), None)
        df = pd.read_csv(f, parse_dates=[parse_date_col] if parse_date_col else False)
        frames.append(df)
        logger.info("retrain.loaded_csv", file=os.path.basename(f), rows=len(df))

    if not frames:
        raise FileNotFoundError(f"No transaction-like CSV files found in {data_dir}")
    if skipped_files:
        logger.info(
            "retrain.skipped_csv_summary",
            skipped_files=skipped_files,
            examples=skipped_examples,
        )

    combined = pd.concat(frames, ignore_index=True)

    # Normalize column names for common Kaggle datasets
    rename_map = {}
    cols_lower = {c.lower(): c for c in combined.columns}

    # Favorita: store_nbr → store_id, family → category, sales → quantity
    if "store_nbr" in cols_lower:
        rename_map[cols_lower["store_nbr"]] = "store_id"
    if "store_code" in cols_lower and "store_id" not in cols_lower:
        rename_map[cols_lower["store_code"]] = "store_id"
    if "family" in cols_lower and "category" not in cols_lower:
        rename_map[cols_lower["family"]] = "category"
    if "sales" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["sales"]] = "quantity"
    if "quantity_sold" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["quantity_sold"]] = "quantity"
    if "qty_sold" in cols_lower and "quantity" not in cols_lower:
        rename_map[cols_lower["qty_sold"]] = "quantity"
    if "transaction_date" in cols_lower and "date" not in cols_lower:
        rename_map[cols_lower["transaction_date"]] = "date"
    if "trans_date" in cols_lower and "date" not in cols_lower:
        rename_map[cols_lower["trans_date"]] = "date"
    if "item_nbr" in cols_lower and "product_id" not in cols_lower:
        rename_map[cols_lower["item_nbr"]] = "product_id"
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

    # Ensure quantity is numeric and drop invalid rows from mixed-source files.
    combined["quantity"] = pd.to_numeric(combined["quantity"], errors="coerce")
    combined = combined.dropna(subset=["store_id", "quantity"])

    # Cast identifiers to strings
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
    trigger: str = "scheduled",
    trigger_metadata: dict | None = None,
):
    """
    Retrain demand forecast model with MLOps integration.

    Modes:
      - Cold-start: Pass data_dir pointing to CSV files (Kaggle/synthetic)
      - Production: Pass customer_id to query DB (future — requires async DB)

    Triggers:
      - "scheduled": Weekly Sunday 2AM (auto-promote if better)
      - "drift_detected": Emergency retrain (challenger only, manual review)
      - "new_products": Incremental update (challenger, test in shadow)
      - "manual": Human-initiated

    Args:
        customer_id: Tenant ID for DB-sourced data (future)
        data_dir: Path to CSV training data directory
        version: Model version string (auto-incremented if None)
        dataset_name: Name for MLflow tracking (e.g., "favorita")
        promote: If True, force promotion (overrides auto-promotion logic)
        trigger: Trigger type for MLOps tracking
        trigger_metadata: Additional context for the trigger
    """
    from ml.features import create_features
    from ml.train import save_models, train_ensemble

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
            tier=features_df.attrs.get("feature_tier", "unknown"),
        )

        # ── Step 3: Train model ──────────────────────────────────────
        settings = get_settings()
        xgb_only_mode = not settings.ml_enable_lstm
        logger.info(
            "retrain.training",
            version=ver,
            dataset=dataset_name,
            xgb_only=xgb_only_mode,
        )
        ensemble_result = train_ensemble(
            features_df=features_df,
            dataset_name=dataset_name,
            version=ver,
            xgb_only=xgb_only_mode,
        )
        ensemble_info = ensemble_result.get("ensemble", {})
        xgb_metrics = ensemble_result.get("xgboost", {}).get("metrics", {})
        metrics = {
            "ensemble_mae": ensemble_info.get("estimated_mae"),
            "ensemble_mape": ensemble_info.get("estimated_mape", xgb_metrics.get("mape")),
            "coverage_90": ensemble_info.get("estimated_coverage_90", xgb_metrics.get("coverage_90")),
        }
        logger.info(
            "retrain.trained",
            version=ver,
            tier=ensemble_info.get("feature_tier", "unknown"),
            mae=metrics.get("ensemble_mae"),
            mape=metrics.get("ensemble_mape"),
        )

        # ── Step 4: Save models + register ───────────────────────────
        save_models(
            ensemble_result=ensemble_result,
            version=ver,
            dataset_name=dataset_name,
            promote=promote,
            rows_trained=len(features_df),
        )
        logger.info("retrain.saved", version=ver, promoted=promote)

        # ── Step 5: MLOps Integration (Champion/Challenger) ──────────
        mlops_result = None
        if customer_id:
            try:
                import asyncio
                import uuid

                from core.config import get_settings
                from ml.arena import evaluate_for_promotion, register_model_version
                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

                async def register_and_evaluate():
                    settings = get_settings()
                    engine = create_async_engine(settings.database_url)
                    try:
                        async_session = async_sessionmaker(engine, class_=AsyncSession)
                        async with async_session() as db:
                            # Set tenant context for RLS
                            await db.execute(f"SET app.current_customer_id = '{customer_id}'")

                            # Register model version in DB
                            model_metrics = {
                                "mae": metrics.get("ensemble_mae"),
                                "mape": metrics.get("ensemble_mape"),
                                "coverage": metrics.get("coverage_90", 0.0) or 0.0,
                                "tier": ensemble_info.get("feature_tier", "unknown"),
                            }

                            model_id = await register_model_version(
                                db=db,
                                customer_id=uuid.UUID(customer_id),
                                model_name="demand_forecast",
                                version=ver,
                                metrics=model_metrics,
                                status="candidate",
                                smoke_test_passed=True,  # Future: add smoke tests
                            )

                            # Auto-promote if better than champion (unless force-promote disabled)
                            if trigger in ("scheduled", "manual"):
                                promotion_result = await evaluate_for_promotion(
                                    db=db,
                                    customer_id=uuid.UUID(customer_id),
                                    model_name="demand_forecast",
                                    candidate_version=ver,
                                    candidate_metrics=model_metrics,
                                    improvement_threshold=0.95,  # 5% improvement required
                                )
                                return {"model_id": str(model_id), "promotion": promotion_result}
                            else:
                                # Drift/new_products triggers → challenger only, no auto-promote
                                return {"model_id": str(model_id), "promotion": {"promoted": False, "reason": f"trigger={trigger}"}}

                    finally:
                        await engine.dispose()

                mlops_result = asyncio.run(register_and_evaluate())
                logger.info("retrain.mlops_integration", **mlops_result)

            except Exception as mlops_exc:
                logger.warning("retrain.mlops_failed", error=str(mlops_exc), exc_info=True)
                # Don't fail the whole job if MLOps integration fails
                mlops_result = {"error": str(mlops_exc)}

        # ── Step 6: Summary ──────────────────────────────────────────
        summary = {
            "status": "success",
            "version": ver,
            "dataset": dataset_name,
            "tier": ensemble_info.get("feature_tier", "unknown"),
            "rows_trained": len(features_df),
            "mae": metrics.get("ensemble_mae"),
            "mape": metrics.get("ensemble_mape"),
            "coverage": metrics.get("coverage_90"),
            "promoted": promote,
            "mlops": mlops_result,
            "trigger": trigger,
            "trigger_metadata": trigger_metadata,
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
