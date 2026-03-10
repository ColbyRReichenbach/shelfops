"""
ML Ops API — Model health, experiments, backtests, and data health.

Endpoints:
  GET /ml/models          — List all model versions with status
  GET /ml/models/{version}/shap — Feature importance for a version
  GET /ml/backtests       — Backtest results time-series
  GET /ml/experiments     — Training run history by model_name
  GET /ml/registry        — Full model registry with iteration history
  GET /ml/health          — Overall ML system health
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import BacktestResult, DemandForecast, ForecastAccuracy, ModelVersion, OpportunityCostLog, Product

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ml", tags=["ml-ops"])

MODEL_DIR = Path(__file__).parent.parent.parent.parent / "models"
REPORTS_DIR = Path(__file__).parent.parent.parent.parent / "reports"


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _round_or_none(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _confidence_label(sample_count: int) -> str:
    if sample_count >= 200:
        return "measured"
    if sample_count >= 50:
        return "estimated"
    return "low_sample"


def _segment_summary(frame: pd.DataFrame, segment_col: str, label: str) -> dict[str, Any]:
    if frame.empty or segment_col not in frame.columns or frame[segment_col].isna().all():
        return {"available": False, "label": label, "segments": []}

    segments = []
    grouped = frame.groupby(segment_col, dropna=False)
    for segment_value, group in grouped:
        actual = group["actual_demand"].astype(float).to_numpy()
        pred = group["forecasted_demand"].astype(float).to_numpy()
        abs_error = abs(pred - actual)
        denom = float(abs(actual).sum())
        mean_actual = float(actual.mean()) if len(actual) else 0.0
        segments.append(
            {
                "segment": str(segment_value),
                "samples": int(len(group)),
                "mae": round(float(abs_error.mean()), 4),
                "wape": round(float(abs_error.sum() / denom), 4) if denom else 0.0,
                "bias_pct": round(float((pred - actual).mean() / mean_actual), 4) if mean_actual else 0.0,
                "stockout_miss_rate": round(float(((group["actual_demand"] > 0) & (group["forecasted_demand"] <= 0)).mean()), 4),
                "overstock_rate": round(float((group["forecasted_demand"] > group["actual_demand"]).mean()), 4),
            }
        )

    segments.sort(key=lambda item: item["samples"], reverse=True)
    return {"available": True, "label": label, "segments": segments[:8]}


# ── Model Registry ────────────────────────────────────────────────────────


@router.get("/models")
async def list_models(
    model_name: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    List all model versions with status (champion/challenger/archived).

    Query params:
      - model_name: Filter by model type (e.g., "demand_forecast_fresh")
      - status: Filter by status (champion, challenger, archived, candidate)
    """
    query = select(ModelVersion).order_by(ModelVersion.created_at.desc())

    if model_name:
        query = query.where(ModelVersion.model_name == model_name)
    if status:
        query = query.where(ModelVersion.status == status)

    result = await db.execute(query)
    versions = result.scalars().all()

    return [
        {
            "model_id": str(v.model_id),
            "model_name": v.model_name,
            "version": v.version,
            "status": v.status,
            "metrics": v.metrics,
            "dataset_id": (v.metrics or {}).get("dataset_id"),
            "forecast_grain": (v.metrics or {}).get("forecast_grain"),
            "segment_strategy": (v.metrics or {}).get("segment_strategy"),
            "feature_set_id": (v.metrics or {}).get("feature_set_id"),
            "architecture": (v.metrics or {}).get("architecture"),
            "objective": (v.metrics or {}).get("objective"),
            "tuning_profile": (v.metrics or {}).get("tuning_profile"),
            "trigger_source": (v.metrics or {}).get("trigger_source"),
            "lineage_label": (v.metrics or {}).get("lineage_label"),
            "rule_overlay_enabled": (v.metrics or {}).get("rule_overlay_enabled"),
            "evaluation_window_days": (v.metrics or {}).get("evaluation_window_days"),
            "promotion_reason": ((v.metrics or {}).get("promotion_decision") or {}).get("reason"),
            "promotion_decision": (v.metrics or {}).get("promotion_decision"),
            "lifecycle_events": (v.metrics or {}).get("lifecycle_events", []),
            "smoke_test_passed": v.smoke_test_passed,
            "routing_weight": v.routing_weight,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "promoted_at": v.promoted_at.isoformat() if v.promoted_at else None,
            "archived_at": v.archived_at.isoformat() if v.archived_at else None,
        }
        for v in versions
    ]


@router.get("/models/{version}/shap")
async def get_model_shap(version: str) -> dict[str, Any]:
    """
    Get SHAP feature importance for a model version.

    Returns top features sorted by importance for bar chart rendering.
    """
    # Check model-specific report dirs first, then global
    search_paths = [
        REPORTS_DIR / f"demand_forecast_{version}" / "feature_importance.json",
        REPORTS_DIR / "demand_forecast" / "feature_importance.json",
        REPORTS_DIR / "feature_importance.json",
    ]

    for path in search_paths:
        if path.exists():
            data = json.loads(path.read_text())
            # Return top 15 features
            sorted_features = sorted(data.items(), key=lambda x: x[1], reverse=True)[:15]
            return {
                "version": version,
                "features": [{"name": k, "importance": round(v, 4)} for k, v in sorted_features],
                "source": str(path),
            }

    return {"version": version, "features": [], "source": None}


# ── Backtests ──────────────────────────────────────────────────────────────


@router.get("/backtests")
async def list_backtests(
    days: int = Query(90, ge=7, le=365),
    model_name: str | None = None,
    db: AsyncSession = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    """
    Get backtest results as time-series for charting.

    Returns walk-forward backtest MAE over time.
    """
    cutoff = date.today() - timedelta(days=days)

    query = (
        select(
            BacktestResult,
            ModelVersion.model_name,
            ModelVersion.version,
        )
        .join(ModelVersion, BacktestResult.model_id == ModelVersion.model_id)
        .where(BacktestResult.forecast_date >= cutoff)
        .order_by(BacktestResult.forecast_date.asc())
    )

    if model_name:
        query = query.where(ModelVersion.model_name == model_name)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "backtest_id": str(backtest.backtest_id),
            "model_name": model_name_value,
            "model_version": model_version,
            "forecast_date": backtest.forecast_date.isoformat() if backtest.forecast_date else None,
            "mae": float(backtest.mae) if backtest.mae is not None else None,
            "mape": float(backtest.mape) if backtest.mape is not None else None,
            "stockout_miss_rate": (
                float(backtest.stockout_miss_rate) if backtest.stockout_miss_rate is not None else None
            ),
            "overstock_rate": float(backtest.overstock_rate) if backtest.overstock_rate is not None else None,
        }
        for backtest, model_name_value, model_version in rows
    ]


# ── Experiment History ─────────────────────────────────────────────────────


@router.get("/experiments")
async def list_experiments(
    model_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    List training run history from local JSON logs.

    Reads from reports/{model_name}/ directories.
    """
    runs = []

    # Scan report directories
    if model_name:
        search_dirs = [REPORTS_DIR / model_name]
    else:
        search_dirs = [REPORTS_DIR]
        if REPORTS_DIR.exists():
            search_dirs.extend(d for d in REPORTS_DIR.iterdir() if d.is_dir())

    for report_dir in search_dirs:
        if not report_dir.exists():
            continue

        for log_file in sorted(report_dir.glob("run_*.json"), reverse=True):
            try:
                data = json.loads(log_file.read_text())
                runs.append(
                    {
                        "experiment": data.get("experiment", "unknown"),
                        "model_name": data.get("model_name", "demand_forecast"),
                        "timestamp": data.get("timestamp"),
                        "params": data.get("params", {}),
                        "metrics": data.get("metrics", {}),
                        "tags": data.get("tags", {}),
                        "mlflow_run_id": data.get("mlflow_run_id"),
                        "source_file": log_file.name,
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue

    return runs[:50]  # Limit to 50 most recent


# ── Model Registry ─────────────────────────────────────────────────────────


@router.get("/registry")
async def get_registry() -> dict[str, Any]:
    """
    Full model registry from local JSON file.

    Shows iteration history from v1 → vN with metrics.
    """
    registry_path = MODEL_DIR / "registry.json"
    if not registry_path.exists():
        return {"models": [], "updated_at": None}

    registry = json.loads(registry_path.read_text())

    # Enrich with file sizes
    for model in registry.get("models", []):
        version = model.get("version", "")
        version_dir = MODEL_DIR / version
        if version_dir.exists():
            files = {}
            for f in version_dir.iterdir():
                files[f.name] = f.stat().st_size
            model["artifacts"] = files

    return registry


# ── ML System Health ───────────────────────────────────────────────────────


@router.get("/health")
async def get_ml_health(
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Overall ML system health dashboard.

    Returns model status, data freshness, and drift indicators.
    """
    # Count models by status
    status_result = await db.execute(
        select(
            ModelVersion.status,
            func.count(ModelVersion.model_id).label("count"),
        ).group_by(ModelVersion.status)
    )
    status_counts = {row.status: row.count for row in status_result.all()}

    # Get champions per model_name
    champion_result = await db.execute(
        select(
            ModelVersion.model_name,
            ModelVersion.version,
            ModelVersion.metrics,
            ModelVersion.promoted_at,
        ).where(ModelVersion.status == "champion")
    )
    champions = [
        {
            "model_name": row.model_name,
            "version": row.version,
            "metrics": row.metrics,
            "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
        }
        for row in champion_result.all()
    ]

    # Recent backtests (last 7 days)
    week_ago = date.today() - timedelta(days=7)
    backtest_result = await db.execute(
        select(func.count(BacktestResult.backtest_id)).where(BacktestResult.forecast_date >= week_ago)
    )
    recent_backtests = backtest_result.scalar() or 0

    if not champions or recent_backtests == 0:
        health_status = "degraded"
    else:
        health_status = "healthy"

    return {
        "status": health_status,
        "model_counts": status_counts,
        "champions": champions,
        "recent_backtests_7d": recent_backtests,
        "registry_exists": (MODEL_DIR / "registry.json").exists(),
        "checked_at": datetime.utcnow().isoformat(),
    }


@router.get("/effectiveness")
async def get_model_effectiveness(
    window_days: int = Query(30, ge=7, le=365),
    model_name: str = Query("demand_forecast"),
    store_id: str | None = Query(None),
    product_id: str | None = Query(None),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Operational model effectiveness summary for rolling windows."""
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    version_rows = (
        await db.execute(
            select(ModelVersion.version, ModelVersion.metrics).where(ModelVersion.model_name == model_name)
        )
    ).all()
    model_versions = [str(row.version) for row in version_rows]
    version_meta = {str(row.version): (row.metrics or {}) for row in version_rows}

    query = (
        select(
            ForecastAccuracy.forecast_date,
            ForecastAccuracy.store_id,
            ForecastAccuracy.product_id,
            ForecastAccuracy.model_version,
            ForecastAccuracy.forecasted_demand,
            ForecastAccuracy.actual_demand,
            ForecastAccuracy.mae,
            ForecastAccuracy.mape,
            DemandForecast.lower_bound,
            DemandForecast.upper_bound,
            Product.category.label("family"),
        )
        .outerjoin(
            DemandForecast,
            (DemandForecast.store_id == ForecastAccuracy.store_id)
            & (DemandForecast.product_id == ForecastAccuracy.product_id)
            & (DemandForecast.forecast_date == ForecastAccuracy.forecast_date)
            & (DemandForecast.model_version == ForecastAccuracy.model_version),
        )
        .outerjoin(Product, Product.product_id == ForecastAccuracy.product_id)
        .where(ForecastAccuracy.evaluated_at >= cutoff)
        .order_by(ForecastAccuracy.forecast_date.asc())
    )

    if model_versions:
        query = query.where(ForecastAccuracy.model_version.in_(model_versions))
    if store_id:
        query = query.where(ForecastAccuracy.store_id == store_id)
    if product_id:
        query = query.where(ForecastAccuracy.product_id == product_id)

    rows = (await db.execute(query)).all()
    if not rows:
        return {
            "window_days": window_days,
            "model_name": model_name,
            "status": "no_data",
            "sample_count": 0,
            "metrics": None,
            "trend": "unknown",
            "confidence": "unavailable",
        }

    frame = pd.DataFrame(
        [
            {
                "forecast_date": row.forecast_date,
                "store_id": str(row.store_id),
                "product_id": str(row.product_id),
                "model_version": str(row.model_version),
                "forecasted_demand": _safe_float(row.forecasted_demand),
                "actual_demand": _safe_float(row.actual_demand),
                "mae": _safe_float(row.mae),
                "mape": _safe_float(row.mape),
                "lower_bound": row.lower_bound,
                "upper_bound": row.upper_bound,
                "family": row.family or "unknown",
            }
            for row in rows
        ]
    )

    sample_count = int(len(frame))
    mae_avg = float(frame["mae"].mean())
    abs_actual_sum = float(frame["actual_demand"].abs().sum())
    mean_actual = float(frame["actual_demand"].mean()) if sample_count else 0.0
    wape = float((frame["forecasted_demand"] - frame["actual_demand"]).abs().sum() / abs_actual_sum) if abs_actual_sum else 0.0
    bias = float((frame["forecasted_demand"] - frame["actual_demand"]).mean() / mean_actual) if mean_actual else 0.0
    seasonality = 7 if sample_count > 7 else 1
    naive_errors = (
        frame["actual_demand"].iloc[seasonality:].reset_index(drop=True)
        - frame["actual_demand"].iloc[:-seasonality].reset_index(drop=True)
    ).abs()
    naive_mae = float(naive_errors.mean()) if len(naive_errors) else 0.0
    mase = float(mae_avg / naive_mae) if naive_mae else 0.0

    stockout_miss_rate = float(((frame["actual_demand"] > 0) & (frame["forecasted_demand"] <= 0)).mean())
    overstock_rate = float((frame["forecasted_demand"] > frame["actual_demand"]).mean())
    coverage_mask = frame["lower_bound"].notna() & frame["upper_bound"].notna()
    coverage = (
        float(
            (
                (frame.loc[coverage_mask, "actual_demand"] >= frame.loc[coverage_mask, "lower_bound"])
                & (frame.loc[coverage_mask, "actual_demand"] <= frame.loc[coverage_mask, "upper_bound"])
            ).mean()
        )
        if coverage_mask.any()
        else None
    )

    midpoint = sample_count // 2
    early_mae = float(frame["mae"].iloc[:midpoint].mean()) if midpoint else mae_avg
    recent_mae = float(frame["mae"].iloc[midpoint:].mean()) if midpoint else mae_avg
    if recent_mae < early_mae * 0.97:
        trend = "improving"
    elif recent_mae > early_mae * 1.03:
        trend = "degrading"
    else:
        trend = "stable"

    confidence = _confidence_label(sample_count)

    opp_query = (
        select(
            OpportunityCostLog.cost_type,
            func.sum(OpportunityCostLog.opportunity_cost).label("opportunity_cost"),
            func.sum(OpportunityCostLog.holding_cost).label("holding_cost"),
            func.sum(OpportunityCostLog.lost_sales_qty).label("lost_sales_qty"),
        )
        .where(OpportunityCostLog.date >= cutoff.date())
        .group_by(OpportunityCostLog.cost_type)
    )
    if store_id:
        opp_query = opp_query.where(OpportunityCostLog.store_id == store_id)
    if product_id:
        opp_query = opp_query.where(OpportunityCostLog.product_id == product_id)
    opp_rows = (await db.execute(opp_query)).all()
    opp_summary = {str(row.cost_type): row for row in opp_rows}

    store_totals = frame.groupby("store_id")["actual_demand"].sum().sort_values()
    if len(store_totals) >= 2:
        ranked = store_totals.rank(method="first")
        bins = min(10, len(store_totals))
        deciles = pd.qcut(ranked, q=bins, labels=False, duplicates="drop") + 1
        store_decile_map = {store_key: f"D{int(decile)}" for store_key, decile in deciles.items()}
    else:
        store_decile_map = {store_key: "D1" for store_key in store_totals.index}
    frame["store_decile"] = frame["store_id"].map(store_decile_map).fillna("D1")

    version_metrics = []
    for version, group in frame.groupby("model_version"):
        version_actual_sum = float(group["actual_demand"].abs().sum())
        version_mean_actual = float(group["actual_demand"].mean()) if len(group) else 0.0
        version_metrics.append(
            {
                "model_version": version,
                "samples": int(len(group)),
                "mae": round(float(group["mae"].mean()), 4),
                "mape_nonzero": round(float(group["mape"].mean()), 4),
                "wape": round(
                    float((group["forecasted_demand"] - group["actual_demand"]).abs().sum() / version_actual_sum),
                    4,
                )
                if version_actual_sum
                else 0.0,
                "mase": round(float(group["mae"].mean() / naive_mae), 4) if naive_mae else 0.0,
                "bias_pct": round(
                    float((group["forecasted_demand"] - group["actual_demand"]).mean() / version_mean_actual),
                    4,
                )
                if version_mean_actual
                else 0.0,
                "forecast_grain": version_meta.get(version, {}).get("forecast_grain"),
                "dataset_id": version_meta.get(version, {}).get("dataset_id"),
                "segment_strategy": version_meta.get(version, {}).get("segment_strategy"),
                "rule_overlay_enabled": version_meta.get(version, {}).get("rule_overlay_enabled"),
                "evaluation_window_days": version_meta.get(version, {}).get("evaluation_window_days"),
            }
        )
    version_metrics.sort(key=lambda item: item["model_version"])

    return {
        "window_days": window_days,
        "model_name": model_name,
        "status": "ok",
        "sample_count": sample_count,
        "trend": trend,
        "confidence": confidence,
        "metrics": {
            "mae": round(mae_avg, 4),
            "mape_nonzero": round(float(frame["mape"].mean()), 4),
            "wape": round(wape, 4),
            "mase": round(mase, 4),
            "bias_pct": round(bias, 4),
            "coverage": round(float(coverage), 4) if coverage is not None else None,
            "stockout_miss_rate": round(stockout_miss_rate, 4),
            "overstock_rate": round(overstock_rate, 4),
            "overstock_dollars": _round_or_none(
                opp_summary.get("overstock").holding_cost if opp_summary.get("overstock") else 0.0,
                2,
            ),
            "opportunity_cost_stockout": _round_or_none(
                opp_summary.get("stockout").opportunity_cost if opp_summary.get("stockout") else 0.0,
                2,
            ),
            "opportunity_cost_overstock": _round_or_none(
                opp_summary.get("overstock").holding_cost if opp_summary.get("overstock") else 0.0,
                2,
            ),
            "lost_sales_qty": _round_or_none(
                opp_summary.get("stockout").lost_sales_qty if opp_summary.get("stockout") else 0.0,
                2,
            ),
        },
        "by_version": version_metrics,
        "forecast_grain": next(
            (meta.get("forecast_grain") for meta in version_meta.values() if meta.get("forecast_grain")),
            None,
        ),
        "evaluation_window": {
            "days": window_days,
            "sample_count": sample_count,
            "start_date": frame["forecast_date"].min().isoformat() if sample_count else None,
            "end_date": frame["forecast_date"].max().isoformat() if sample_count else None,
        },
        "segment_breakdowns": {
            "family": _segment_summary(frame, "family", "family"),
            "store_decile": _segment_summary(frame, "store_decile", "store_decile"),
            "promo": {
                "available": False,
                "label": "promo",
                "segments": [],
                "reason": "promotion flags are not stored on ForecastAccuracy rows",
            },
        },
        "window_start": cutoff.date().isoformat(),
        "window_end": datetime.utcnow().date().isoformat(),
    }
