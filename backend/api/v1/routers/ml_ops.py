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

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_tenant_db
from db.models import BacktestResult, DemandForecast, ForecastAccuracy, ModelVersion

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/ml", tags=["ml-ops"])

MODEL_DIR = Path(__file__).parent.parent.parent.parent / "models"
REPORTS_DIR = Path(__file__).parent.parent.parent.parent / "reports"


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

    return {
        "status": "healthy",
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
    """
    Operational model effectiveness summary for rolling windows.

    Uses live ForecastAccuracy rows and joins prediction intervals from DemandForecast
    to compute coverage.
    """
    cutoff = datetime.utcnow() - timedelta(days=window_days)

    versions_query = await db.execute(
        select(ModelVersion.version).where(ModelVersion.model_name == model_name)
    )
    model_versions = [str(row.version) for row in versions_query.all()]

    query = (
        select(
            ForecastAccuracy.forecast_date,
            ForecastAccuracy.model_version,
            ForecastAccuracy.forecasted_demand,
            ForecastAccuracy.actual_demand,
            ForecastAccuracy.mae,
            ForecastAccuracy.mape,
            DemandForecast.lower_bound,
            DemandForecast.upper_bound,
        )
        .outerjoin(
            DemandForecast,
            (DemandForecast.store_id == ForecastAccuracy.store_id)
            & (DemandForecast.product_id == ForecastAccuracy.product_id)
            & (DemandForecast.forecast_date == ForecastAccuracy.forecast_date)
            & (DemandForecast.model_version == ForecastAccuracy.model_version),
        )
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

    def _safe_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    sample_count = len(rows)
    mae_values = [_safe_float(r.mae) for r in rows]
    mape_values = [_safe_float(r.mape) for r in rows]

    stockout_misses = 0
    overstock = 0
    covered = 0
    coverage_denominator = 0
    for row in rows:
        actual = _safe_float(row.actual_demand)
        forecasted = _safe_float(row.forecasted_demand)
        if actual > 0 and forecasted <= 0:
            stockout_misses += 1
        if forecasted > actual:
            overstock += 1
        if row.lower_bound is not None and row.upper_bound is not None:
            coverage_denominator += 1
            if _safe_float(row.lower_bound) <= actual <= _safe_float(row.upper_bound):
                covered += 1

    mae_avg = sum(mae_values) / sample_count
    mape_avg = sum(mape_values) / sample_count
    stockout_miss_rate = stockout_misses / sample_count
    overstock_rate = overstock / sample_count
    coverage = (covered / coverage_denominator) if coverage_denominator > 0 else None

    midpoint = sample_count // 2
    early = mae_values[:midpoint] if midpoint else mae_values
    recent = mae_values[midpoint:] if midpoint else mae_values
    early_mae = (sum(early) / len(early)) if early else mae_avg
    recent_mae = (sum(recent) / len(recent)) if recent else mae_avg
    if recent_mae < early_mae * 0.97:
        trend = "improving"
    elif recent_mae > early_mae * 1.03:
        trend = "degrading"
    else:
        trend = "stable"

    if sample_count >= 200:
        confidence = "measured"
    elif sample_count >= 50:
        confidence = "estimated"
    else:
        confidence = "low_sample"

    by_version: dict[str, dict[str, float | int]] = {}
    for row in rows:
        key = str(row.model_version)
        item = by_version.setdefault(key, {"samples": 0, "mae_sum": 0.0, "mape_sum": 0.0})
        item["samples"] += 1
        item["mae_sum"] += _safe_float(row.mae)
        item["mape_sum"] += _safe_float(row.mape)

    version_metrics = [
        {
            "model_version": version,
            "samples": values["samples"],
            "mae": round(values["mae_sum"] / values["samples"], 4) if values["samples"] else None,
            "mape_nonzero": round(values["mape_sum"] / values["samples"], 4) if values["samples"] else None,
        }
        for version, values in sorted(by_version.items())
    ]

    return {
        "window_days": window_days,
        "model_name": model_name,
        "status": "ok",
        "sample_count": sample_count,
        "trend": trend,
        "confidence": confidence,
        "metrics": {
            "mae": round(mae_avg, 4),
            "mape_nonzero": round(mape_avg, 4),
            "coverage": round(float(coverage), 4) if coverage is not None else None,
            "stockout_miss_rate": round(stockout_miss_rate, 4),
            "overstock_rate": round(overstock_rate, 4),
        },
        "by_version": version_metrics,
        "window_start": cutoff.date().isoformat(),
        "window_end": datetime.utcnow().date().isoformat(),
    }
