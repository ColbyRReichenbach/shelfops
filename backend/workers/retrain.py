"""
ML Retraining Workers — Scheduled model retraining.

Runs the full ML pipeline:
  1. Load training data (CSV cold-start or DB query)
  2. Feature engineering (auto-detects tier)
  3. Train XGBoost + LSTM ensemble
  4. Save models + register in model registry
  5. Refresh alerts with updated forecasts
"""

import glob
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from ml.contract_mapper import build_canonical_result
from ml.contract_profiles import ContractProfile, load_contract_profile
from ml.data_contracts import load_canonical_transactions
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
    path = Path(data_dir)
    canonical_csv = path / "canonical_transactions.csv"

    # Profile-driven onboarding flow writes canonical CSV for retraining.
    if canonical_csv.exists():
        combined = pd.read_csv(canonical_csv, parse_dates=["date"], low_memory=False)
    else:
        combined = load_canonical_transactions(data_dir)

    logger.info(
        "retrain.data_ready",
        rows=len(combined),
        stores=combined["store_id"].nunique(),
        products=combined["product_id"].nunique(),
        date_range=f"{combined['date'].min()} → {combined['date'].max()}",
        dataset_id=combined["dataset_id"].iloc[0] if len(combined) > 0 else "unknown",
        frequency=combined["frequency"].iloc[0] if len(combined) > 0 else "unknown",
    )
    return combined


def _load_profiled_data(contract_path: str, sample_path: str, output_dir: str) -> pd.DataFrame:
    """
    Load raw source data using a versioned contract profile and persist canonical output.
    """
    profile = load_contract_profile(contract_path)
    sample = Path(sample_path)

    if sample.is_dir():
        # Prefer explicit transaction/sales extracts over master/reference files.
        preferred_names = ["transactions.csv", "sales.csv", "daily_sales.csv"]
        preferred = [sample / name for name in preferred_names if (sample / name).exists()]
        if preferred:
            csvs = preferred
        else:
            csvs = sorted(
                p
                for p in sample.glob("*.csv")
                if p.name.lower() not in {"stores.csv", "products.csv", "store_master.csv", "product_master.csv"}
            )
        if not csvs:
            raise FileNotFoundError(f"No CSV files found in sample directory: {sample}")
        raw = pd.concat([pd.read_csv(p, low_memory=False) for p in csvs], ignore_index=True)
    else:
        if sample.suffix.lower() == ".csv":
            raw = pd.read_csv(sample, low_memory=False)
        elif sample.suffix.lower() in {".json", ".jsonl"}:
            raw = pd.read_json(sample, lines=True)
        else:
            raise ValueError(f"Unsupported sample file type for profiled load: {sample.suffix}")

    result = build_canonical_result(raw, profile)
    if not result.report.passed:
        raise ValueError(f"Contract validation failed: {'; '.join(result.report.failures)}")

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    canonical_path = target_dir / "canonical_transactions.csv"
    result.dataframe.to_csv(canonical_path, index=False)
    report_json = target_dir / "contract_validation_report.json"
    report_md = target_dir / "contract_validation_report.md"
    report_payload = {
        "contract_path": str(Path(contract_path).resolve()),
        "sample_path": str(sample.resolve()),
        "rows_mapped": int(len(result.dataframe)),
        "report": result.report.to_dict(),
        "cost_field_coverage": {
            "unit_cost_non_null_rate": (
                float(result.dataframe["unit_cost"].notna().mean()) if "unit_cost" in result.dataframe.columns else 0.0
            ),
            "unit_price_non_null_rate": (
                float(result.dataframe["unit_price"].notna().mean())
                if "unit_price" in result.dataframe.columns
                else 0.0
            ),
        },
    }
    report_json.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    report_md.write_text(
        "\n".join(
            [
                "# Contract Validation Report",
                "",
                f"- Contract: `{report_payload['contract_path']}`",
                f"- Sample: `{report_payload['sample_path']}`",
                f"- Rows mapped: {report_payload['rows_mapped']}",
                f"- Passed: `{report_payload['report']['passed']}`",
                "",
                "## Data Quality Metrics",
                "",
                f"- date_parse_success: {report_payload['report']['metrics'].get('date_parse_success', 0):.4f}",
                f"- required_null_rate: {report_payload['report']['metrics'].get('required_null_rate', 0):.4f}",
                f"- duplicate_rate: {report_payload['report']['metrics'].get('duplicate_rate', 0):.4f}",
                f"- quantity_parse_success: {report_payload['report']['metrics'].get('quantity_parse_success', 0):.4f}",
                "",
                "## Cost Field Coverage",
                "",
                f"- unit_cost_non_null_rate: {report_payload['cost_field_coverage']['unit_cost_non_null_rate']:.4f}",
                f"- unit_price_non_null_rate: {report_payload['cost_field_coverage']['unit_price_non_null_rate']:.4f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    logger.info(
        "retrain.profiled_data_ready",
        tenant_id=profile.tenant_id,
        source_type=profile.source_type,
        rows=len(result.dataframe),
        canonical_path=str(canonical_path),
        validation_report_json=str(report_json),
        validation_report_md=str(report_md),
    )
    return result.dataframe


def _db_contract_profile(customer_id: str) -> ContractProfile:
    return ContractProfile(
        contract_version="v1",
        tenant_id=customer_id,
        source_type="enterprise_event",
        grain="daily",
        timezone="UTC",
        timezone_handling="convert_to_profile_tz_date",
        quantity_sign_policy="allow_negative_returns",
        id_columns={"store_id": "store_id", "product_id": "product_id"},
        field_map={
            "date": "date",
            "store_id": "store_id",
            "product_id": "product_id",
            "quantity": "quantity",
            "category": "category",
            "unit_cost": "unit_cost",
            "unit_price": "unit_price",
            "is_promotional": "is_promotional",
            "is_holiday": "is_holiday",
            "transaction_type": "transaction_type",
        },
        type_map={
            "date": "date",
            "store_id": "str",
            "product_id": "str",
            "quantity": "float",
            "category": "str",
            "unit_cost": "float",
            "unit_price": "float",
            "is_promotional": "bool",
            "is_holiday": "bool",
            "transaction_type": "str",
        },
        unit_map={"quantity": {"multiplier": 1.0}},
        null_policy={},
        dedupe_keys=["store_id", "product_id", "date"],
        dq_thresholds={
            "min_date_parse_success": 0.99,
            "max_required_null_rate": 0.005,
            "max_duplicate_rate": 0.01,
            "min_quantity_parse_success": 0.995,
        },
        country_code="US",
    )


def _load_db_data(
    customer_id: str,
    min_rows: int = 90,
    raw_override: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Load tenant transaction history from the production DB, normalize via
    contract mapper, and enforce minimum data sufficiency checks.
    """
    import asyncio

    from sqlalchemy import case, func, select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from core.config import get_settings
    from db.models import Product, Transaction

    async def _query() -> pd.DataFrame:
        settings = get_settings()
        engine = create_async_engine(settings.database_url)
        try:
            session_factory = async_sessionmaker(engine, class_=AsyncSession)
            async with session_factory() as db:
                try:
                    await db.execute(
                        text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                        {"customer_id": customer_id},
                    )
                except Exception:
                    # SQLite test harness does not support set_config.
                    pass

                signed_quantity = case(
                    (Transaction.transaction_type == "sale", func.abs(Transaction.quantity)),
                    (Transaction.transaction_type == "return", -func.abs(Transaction.quantity)),
                    else_=0,
                )

                sales_date = func.date(Transaction.timestamp)
                result = await db.execute(
                    select(
                        sales_date.label("date"),
                        Transaction.store_id.label("store_id"),
                        Transaction.product_id.label("product_id"),
                        func.sum(signed_quantity).label("quantity"),
                        func.max(Product.category).label("category"),
                        func.max(Product.unit_cost).label("unit_cost"),
                        func.max(Transaction.unit_price).label("unit_price"),
                    )
                    .join(Product, Product.product_id == Transaction.product_id)
                    .where(
                        Transaction.customer_id == uuid.UUID(customer_id),
                        Transaction.transaction_type.in_(["sale", "return"]),
                    )
                    .group_by(sales_date, Transaction.store_id, Transaction.product_id)
                    .order_by(sales_date.asc())
                )
                rows = result.all()

                if not rows:
                    return pd.DataFrame()

                return pd.DataFrame(
                    [
                        {
                            "date": row.date,
                            "store_id": str(row.store_id),
                            "product_id": str(row.product_id),
                            "quantity": float(row.quantity or 0.0),
                            "category": row.category or "unknown",
                            "unit_cost": float(row.unit_cost) if row.unit_cost is not None else None,
                            "unit_price": float(row.unit_price) if row.unit_price is not None else None,
                            "is_promotional": 0,
                            "is_holiday": 0,
                        }
                        for row in rows
                    ]
                )
        finally:
            await engine.dispose()

    raw = raw_override.copy() if raw_override is not None else asyncio.run(_query())
    if raw.empty:
        raise ValueError(f"No transaction history found in DB for customer_id={customer_id}")

    profile = _db_contract_profile(customer_id)
    mapped = build_canonical_result(raw, profile)
    if not mapped.report.passed:
        raise ValueError(f"DB canonical validation failed: {'; '.join(mapped.report.failures)}")

    canonical = mapped.dataframe.copy()
    if len(canonical) < min_rows:
        raise ValueError(f"Insufficient training rows ({len(canonical)} < {min_rows}) for customer_id={customer_id}")
    if canonical["store_id"].nunique() < 1 or canonical["product_id"].nunique() < 1:
        raise ValueError("Insufficient store/product diversity for retraining")

    logger.info(
        "retrain.db_data_ready",
        customer_id=customer_id,
        rows=len(canonical),
        stores=int(canonical["store_id"].nunique()),
        products=int(canonical["product_id"].nunique()),
        date_range=f"{canonical['date'].min()} → {canonical['date'].max()}",
    )
    return canonical


def _candidate_metrics_from_holdout(features_df: pd.DataFrame, ensemble_result: dict) -> dict:
    from ml.metrics_contract import compute_forecast_metrics, coverage_rate
    from ml.train import TARGET_COL

    if TARGET_COL not in features_df.columns:
        raise ValueError(f"Missing target column '{TARGET_COL}' in features_df")

    feature_cols = [c for c in ensemble_result.get("ensemble", {}).get("feature_cols", []) if c in features_df.columns]
    if not feature_cols:
        raise ValueError("No feature columns available for holdout metric computation")

    n_rows = len(features_df)
    split = int(n_rows * 0.8)
    if n_rows < 50 or split <= 0 or split >= n_rows:
        raise ValueError(f"Insufficient rows for holdout evaluation (rows={n_rows})")

    train_part = features_df.iloc[:split].copy()
    eval_part = features_df.iloc[split:].copy()
    if len(eval_part) < 10:
        raise ValueError(f"Insufficient holdout rows for evaluation (rows={len(eval_part)})")

    model = ensemble_result["xgboost"]["model"]
    X_train = train_part[feature_cols].fillna(0)
    y_train = pd.to_numeric(train_part[TARGET_COL], errors="coerce").fillna(0.0)
    X_eval = eval_part[feature_cols].fillna(0)
    y_eval = pd.to_numeric(eval_part[TARGET_COL], errors="coerce").fillna(0.0)

    train_preds = np.maximum(model.predict(X_train), 0)
    eval_preds = np.maximum(model.predict(X_eval), 0)

    residual_abs = np.abs(y_train.values - train_preds)
    interval_width = float(np.quantile(residual_abs, 0.9)) if len(residual_abs) else 0.0
    lower_bound = np.maximum(eval_preds - interval_width, 0)
    upper_bound = eval_preds + interval_width

    metric_bundle = compute_forecast_metrics(
        y_eval,
        eval_preds,
        unit_cost=eval_part["unit_cost"] if "unit_cost" in eval_part.columns else None,
    )

    return {
        "mae": float(metric_bundle["mae"]),
        "mape": float(metric_bundle["mape_nonzero"]),
        "coverage": float(coverage_rate(y_eval, lower_bound, upper_bound)),
        "stockout_miss_rate": float(metric_bundle["stockout_miss_rate"]),
        "overstock_rate": float(metric_bundle["overstock_rate"]),
        "overstock_dollars": metric_bundle["overstock_dollars"],
        "overstock_dollars_confidence": metric_bundle["overstock_dollars_confidence"],
        "eval_rows": int(len(eval_part)),
        "interval_q90_width": interval_width,
    }


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
    model_name: str = "demand_forecast",
    category_tier: str | None = None,
    contract_path: str | None = None,
    sample_path: str | None = None,
    canonical_output_dir: str | None = None,
):
    """
    Retrain demand forecast model with MLOps integration.

    Supports global and category-specific model retraining.

    Modes:
      - Cold-start: Pass data_dir pointing to CSV files (Kaggle/synthetic)
      - Production: Pass customer_id to query tenant DB and normalize via contract mapper.

    Triggers:
      - "scheduled": Weekly Sunday 2AM (auto-promote if better)
      - "drift_detected": Emergency retrain (challenger only, manual review)
      - "new_products": Incremental update (challenger, test in shadow)
      - "manual": Human-initiated

    Args:
        customer_id: Tenant ID for DB-sourced retraining
        data_dir: Path to CSV training data directory
        version: Model version string (auto-incremented if None)
        dataset_name: Name for MLflow tracking (e.g., "favorita")
        promote: If True, force promotion (overrides auto-promotion logic)
        trigger: Trigger type for MLOps tracking
        trigger_metadata: Additional context for the trigger
        model_name: Model identifier for registry (e.g., "demand_forecast_fresh")
        category_tier: If set, filter data to this tier's categories
        contract_path: Optional YAML contract profile for tenant onboarding source mapping
        sample_path: Optional raw sample path (CSV/JSONL/directory) used with contract_path
        canonical_output_dir: Optional output directory for canonicalized CSV
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
        if contract_path and sample_path:
            output_dir = canonical_output_dir or os.path.join("data", "canonical", customer_id or "local")
            transactions_df = _load_profiled_data(contract_path, sample_path, output_dir)
            dataset_name = dataset_name if dataset_name != "unknown" else "contract_profiled"
        elif data_dir:
            transactions_df = _load_csv_data(data_dir)
        elif customer_id:
            transactions_df = _load_db_data(customer_id)
            dataset_name = dataset_name if dataset_name != "unknown" else "tenant_db"
        else:
            # Local fallback mode for ad-hoc training when no DB customer context exists.
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

        # ── Step 1b: Filter by category tier (if training tier-specific model)
        if category_tier:
            from ml.segmentation import get_tier_categories

            tier_categories = get_tier_categories(category_tier)
            if "category" in transactions_df.columns:
                transactions_df = transactions_df[transactions_df["category"].isin(tier_categories)]
                logger.info(
                    "retrain.filtered_by_tier",
                    tier=category_tier,
                    categories=tier_categories,
                    rows=len(transactions_df),
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
            model_name=model_name,
        )
        xgb_metrics = ensemble_result.get("xgboost", {}).get("metrics", {})
        logger.info(
            "retrain.trained",
            version=ver,
            tier=ensemble_result.get("ensemble", {}).get("feature_tier", "unknown"),
            mae=xgb_metrics.get("mae"),
            mape=xgb_metrics.get("mape"),
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

                from sqlalchemy import text, update
                from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

                from core.config import get_settings
                from db.models import ModelVersion
                from ml.arena import evaluate_for_promotion, register_model_version

                model_metrics = _candidate_metrics_from_holdout(features_df, ensemble_result)
                model_metrics["tier"] = ensemble_result.get("ensemble", {}).get("feature_tier", "unknown")
                smoke_test_passed = bool(
                    model_metrics.get("eval_rows", 0) >= 10
                    and model_metrics.get("mae") is not None
                    and model_metrics.get("mape") is not None
                    and model_metrics.get("coverage") is not None
                )

                async def register_and_evaluate():
                    settings = get_settings()
                    engine = create_async_engine(settings.database_url)
                    try:
                        async_session = async_sessionmaker(engine, class_=AsyncSession)
                        async with async_session() as db:
                            # Set tenant context for RLS
                            try:
                                await db.execute(
                                    text("SELECT set_config('app.current_customer_id', :customer_id, false)"),
                                    {"customer_id": customer_id},
                                )
                            except Exception:
                                # SQLite test harness does not support set_config.
                                pass

                            # Register model version in DB
                            model_id = await register_model_version(
                                db=db,
                                customer_id=uuid.UUID(customer_id),
                                model_name=model_name,
                                version=ver,
                                metrics=model_metrics,
                                status="candidate",
                                smoke_test_passed=smoke_test_passed,
                            )

                            # Promotion gate is fail-closed on missing business metrics.
                            if model_metrics.get("overstock_dollars") is None:
                                blocked_metrics = dict(model_metrics)
                                blocked_metrics["promotion_block_reason"] = "blocked_missing_business_metrics"
                                await db.execute(
                                    update(ModelVersion)
                                    .where(
                                        ModelVersion.customer_id == uuid.UUID(customer_id),
                                        ModelVersion.model_name == model_name,
                                        ModelVersion.version == ver,
                                    )
                                    .values(
                                        status="challenger",
                                        routing_weight=0.0,
                                        metrics=blocked_metrics,
                                    )
                                )
                                await db.commit()
                                return {
                                    "model_id": str(model_id),
                                    "promotion": {
                                        "promoted": False,
                                        "reason": "blocked_missing_business_metrics",
                                    },
                                }

                            # Auto-promote if better than champion (unless force-promote disabled)
                            if trigger in ("scheduled", "manual"):
                                promotion_result = await evaluate_for_promotion(
                                    db=db,
                                    customer_id=uuid.UUID(customer_id),
                                    model_name=model_name,
                                    candidate_version=ver,
                                    candidate_metrics=model_metrics,
                                )
                                return {"model_id": str(model_id), "promotion": promotion_result}
                            else:
                                # Drift/new_products triggers → challenger only, no auto-promote
                                return {
                                    "model_id": str(model_id),
                                    "promotion": {"promoted": False, "reason": f"trigger={trigger}"},
                                }

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
            "model_name": model_name,
            "category_tier": category_tier,
            "dataset": dataset_name,
            "tier": ensemble_result.get("ensemble", {}).get("feature_tier", "unknown"),
            "rows_trained": len(features_df),
            "mae": xgb_metrics.get("mae"),
            "mape": xgb_metrics.get("mape"),
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
