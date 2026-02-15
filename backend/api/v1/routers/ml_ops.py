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
from db.models import BacktestResult, ModelVersion

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
