"""
MLflow Experiment Tracking — Wrapper for consistent logging.

Every training run MUST be logged. This module provides a clean
interface so train.py doesn't need to know MLflow internals.

Usage:
    with ExperimentTracker("demand_forecast") as tracker:
        tracker.log_params({"n_estimators": 500, "feature_tier": "cold_start"})
        model, metrics = train_xgboost(features_df)
        tracker.log_metrics(metrics)
        tracker.log_model(model, "xgboost")
        tracker.log_feature_importance(model, feature_cols)
"""

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# MLflow import with graceful fallback
try:
    import mlflow
    import mlflow.sklearn
    import mlflow.xgboost

    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("mlflow not installed — experiment tracking disabled")


# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
DEFAULT_EXPERIMENT_NAME = "shelfops_demand_forecast"
MODEL_DIR = Path(__file__).parent.parent / "models"
REPORTS_DIR = Path(__file__).parent.parent / "reports"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
MODEL_PERFORMANCE_LOG_PATH = REPORTS_DIR / "MODEL_PERFORMANCE_LOG.md"

# Legacy alias
EXPERIMENT_NAME = DEFAULT_EXPERIMENT_NAME


# ──────────────────────────────────────────────────────────────────────
# Registry Helpers
# ──────────────────────────────────────────────────────────────────────


def _load_registry() -> dict[str, Any]:
    """Load model registry JSON."""
    registry_path = MODEL_DIR / "registry.json"
    if registry_path.exists():
        return json.loads(registry_path.read_text())
    return {"models": [], "updated_at": None}


def _save_registry(registry: dict[str, Any]) -> None:
    """Save model registry JSON."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now(timezone.utc).isoformat()
    (MODEL_DIR / "registry.json").write_text(json.dumps(registry, indent=2, default=str))


def _refresh_model_performance_log(registry: dict[str, Any] | None = None) -> None:
    """
    Auto-generate the model performance decision log markdown.

    This runs on every model registration so champion/challenger state and
    promotion decisions are always tracked without manual steps.
    """
    if registry is None:
        registry = _load_registry()

    champion_path = MODEL_DIR / "champion.json"
    champion = {}
    if champion_path.exists():
        champion = json.loads(champion_path.read_text(encoding="utf-8"))
    champion_version = champion.get("version")

    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# Model Performance Log",
        "",
        f"_Generated at: {generated_at}_",
        "",
        "This file is auto-generated during model registration (`register_model`).",
        "",
        "## Data Sources",
        "",
        "- `backend/models/registry.json`",
        "- `backend/models/champion.json`",
        "",
        "## Decision Log",
        "",
        "| order | version | model_name | dataset | tier | rows_trained | mae | mape | status | trained_at | promoted_at | decision | decision_basis |",
        "|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---|",
    ]

    rows = registry.get("models", [])
    for idx, row in enumerate(rows, start=1):
        status = row.get("status", "unknown")
        version = row.get("version", "unknown")

        if status == "champion" and version == champion_version:
            decision = "promoted_to_champion"
            basis = "status=champion and champion pointer matches"
        elif status == "champion":
            decision = "historic_champion"
            basis = "status=champion in registry"
        elif status == "candidate":
            decision = "candidate_pending"
            basis = "registered but not promoted yet"
        elif status == "challenger":
            decision = "challenger_shadow"
            basis = "candidate held for challenger/shadow evaluation"
        elif status == "archived":
            decision = "archived"
            basis = "superseded by newer champion"
        else:
            decision = "unknown"
            basis = "status not mapped"

        mae = row.get("mae")
        mape = row.get("mape")
        mae_s = f"{mae:.6f}" if isinstance(mae, (int, float)) else "-"
        mape_s = f"{mape:.6f}" if isinstance(mape, (int, float)) else "-"

        lines.append(
            f"| {idx} | {version} | {row.get('model_name', 'demand_forecast')} | {row.get('dataset', 'unknown')} | "
            f"{row.get('feature_tier', 'unknown')} | {row.get('rows_trained', '-')} | {mae_s} | {mape_s} | "
            f"{status} | {row.get('trained_at', '-')} | {row.get('promoted_at', '-')} | {decision} | {basis} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This log is append-only through `registry.json` updates.",
            "- Runtime champion/challenger truth in production comes from Postgres model tables.",
        ]
    )

    MODEL_PERFORMANCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PERFORMANCE_LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("model.performance_log_refreshed", path=str(MODEL_PERFORMANCE_LOG_PATH))


def register_model(
    version: str,
    feature_tier: str,
    dataset: str,
    rows_trained: int,
    metrics: dict[str, float],
    promote: bool = False,
    model_name: str = "demand_forecast",
) -> None:
    """Add a model version to the registry."""
    registry = _load_registry()

    entry = {
        "version": version,
        "model_name": model_name,
        "feature_tier": feature_tier,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "rows_trained": rows_trained,
        "mae": metrics.get("mae"),
        "mape": metrics.get("mape"),
        "status": "champion" if promote else "candidate",
        "promoted_at": datetime.now(timezone.utc).isoformat() if promote else None,
    }

    # Demote existing champion if promoting new one
    if promote:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        for m in registry["models"]:
            if m["status"] == "champion":
                m["status"] = "archived"
        # Update champion pointer
        (MODEL_DIR / "champion.json").write_text(
            json.dumps({"version": version, "promoted_at": entry["promoted_at"]}, indent=2)
        )

    registry["models"].append(entry)
    _save_registry(registry)
    try:
        _refresh_model_performance_log(registry)
    except Exception as e:
        logger.warning("model.performance_log_refresh_failed", error=str(e))
    logger.info("model.registered", version=version, status=entry["status"])


def sync_registry_with_runtime_state(
    *,
    version: str,
    model_name: str,
    candidate_status: str | None,
    active_champion_version: str | None,
    promotion_reason: str | None = None,
) -> None:
    """
    Reconcile file-based registry/champion artifacts with DB runtime state.

    This keeps `registry.json`, `champion.json`, and the generated model
    performance log aligned with Postgres model lifecycle truth.
    """
    registry = _load_registry()
    models = registry.get("models", [])

    target_row = None
    for row in reversed(models):
        if row.get("version") == version and row.get("model_name", "demand_forecast") == model_name:
            target_row = row
            break

    if target_row is None:
        logger.warning(
            "model.registry_sync_missing_version",
            version=version,
            model_name=model_name,
        )
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    if candidate_status:
        target_row["status"] = candidate_status
        if candidate_status == "champion":
            target_row["promoted_at"] = target_row.get("promoted_at") or now_iso
        elif candidate_status in {"candidate", "challenger", "shadow", "archived"}:
            target_row["promoted_at"] = None

    if promotion_reason:
        target_row["promotion_reason"] = promotion_reason

    champion_promoted_at = None
    for row in models:
        if row.get("model_name", "demand_forecast") != model_name:
            continue
        if active_champion_version and row.get("version") == active_champion_version:
            row["status"] = "champion"
            row["promoted_at"] = row.get("promoted_at") or now_iso
            champion_promoted_at = row["promoted_at"]
        elif row.get("status") == "champion":
            row["status"] = "archived"

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    champion_path = MODEL_DIR / "champion.json"
    if active_champion_version:
        champion_payload = {
            "version": active_champion_version,
            "promoted_at": champion_promoted_at or now_iso,
        }
        champion_path.write_text(json.dumps(champion_payload, indent=2), encoding="utf-8")
    elif champion_path.exists():
        champion_path.unlink()

    _save_registry(registry)
    try:
        _refresh_model_performance_log(registry)
    except Exception as e:
        logger.warning("model.performance_log_refresh_failed", error=str(e))

    logger.info(
        "model.registry_synced_with_runtime",
        version=version,
        model_name=model_name,
        candidate_status=candidate_status,
        active_champion_version=active_champion_version,
    )


# ──────────────────────────────────────────────────────────────────────
# Experiment Tracker
# ──────────────────────────────────────────────────────────────────────


class ExperimentTracker:
    """
    Context manager for MLflow experiment tracking.

    Falls back to local JSON logging if MLflow is unavailable.
    """

    def __init__(self, experiment_name: str | None = None, model_name: str = "demand_forecast"):
        self.model_name = model_name
        self.experiment_name = experiment_name or f"shelfops_{model_name}"
        self.run = None
        self.start_time = None
        self.local_log: dict[str, Any] = {}

    def __enter__(self):
        self.start_time = time.time()

        if MLFLOW_AVAILABLE:
            try:
                mlflow.set_tracking_uri(TRACKING_URI)
                mlflow.set_experiment(self.experiment_name)
                self.run = mlflow.start_run()
                logger.info(
                    "mlflow.run_started",
                    run_id=self.run.info.run_id,
                    experiment=self.experiment_name,
                )
            except Exception as e:
                logger.warning("mlflow.connection_failed", error=str(e))
                self.run = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        self.log_metrics({"training_time_sec": round(elapsed, 1)})

        if self.run:
            try:
                if exc_type:
                    mlflow.set_tag("status", "failed")
                    mlflow.set_tag("error", str(exc_val))
                else:
                    mlflow.set_tag("status", "completed")
                mlflow.end_run()
            except Exception:
                pass

        # Always save local log as fallback
        self._save_local_log()
        return False  # Don't suppress exceptions

    def log_params(self, params: dict[str, Any]) -> None:
        """Log hyperparameters and configuration."""
        self.local_log.setdefault("params", {}).update(params)
        if self.run:
            try:
                mlflow.log_params({k: str(v) for k, v in params.items()})
            except Exception as e:
                logger.warning("mlflow.log_params_failed", error=str(e))

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log numeric metrics."""
        self.local_log.setdefault("metrics", {}).update(metrics)
        if self.run:
            try:
                mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
            except Exception as e:
                logger.warning("mlflow.log_metrics_failed", error=str(e))

    def log_tags(self, tags: dict[str, str]) -> None:
        """Log string tags (tier, dataset, trigger)."""
        self.local_log.setdefault("tags", {}).update(tags)
        if self.run:
            try:
                mlflow.set_tags(tags)
            except Exception as e:
                logger.warning("mlflow.log_tags_failed", error=str(e))

    def log_artifact(self, filepath: str | Path) -> None:
        """Log a file as an artifact."""
        self.local_log.setdefault("artifacts", []).append(str(filepath))
        if self.run:
            try:
                mlflow.log_artifact(str(filepath))
            except Exception as e:
                logger.warning("mlflow.log_artifact_failed", error=str(e))

    def log_model(self, model: Any, model_name: str) -> None:
        """Log a trained model artifact."""
        if self.run:
            try:
                if model_name == "xgboost":
                    mlflow.xgboost.log_model(model, model_name)
                else:
                    mlflow.sklearn.log_model(model, model_name)
            except Exception as e:
                logger.warning("mlflow.log_model_failed", error=str(e))

    def log_feature_importance(self, model: Any, feature_cols: list[str]) -> Path | None:
        """Log feature importance as JSON artifact."""
        try:
            if hasattr(model, "feature_importances_"):
                importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
            elif hasattr(model, "get_score"):
                importance = model.get_score(importance_type="gain")
            else:
                return None

            # Sort descending
            importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

            report_dir = REPORTS_DIR / self.model_name
            report_dir.mkdir(parents=True, exist_ok=True)
            out_path = report_dir / "feature_importance.json"
            out_path.write_text(json.dumps(importance, indent=2))
            self.log_artifact(out_path)
            return out_path

        except Exception as e:
            logger.warning("feature_importance.failed", error=str(e))
            return None

    def _save_local_log(self) -> None:
        """Save run log to model-specific report directory."""
        report_dir = REPORTS_DIR / self.model_name
        report_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = report_dir / f"run_{timestamp}.json"
        self.local_log["timestamp"] = timestamp
        self.local_log["experiment"] = self.experiment_name
        self.local_log["model_name"] = self.model_name
        if self.run:
            self.local_log["mlflow_run_id"] = self.run.info.run_id
        log_path.write_text(json.dumps(self.local_log, indent=2, default=str))
        logger.info("experiment.local_log_saved", path=str(log_path), model_name=self.model_name)
