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
EXPERIMENT_NAME = "shelfops_demand_forecast"
MODEL_DIR = Path(__file__).parent.parent / "models"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


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


def register_model(
    version: str,
    feature_tier: str,
    dataset: str,
    rows_trained: int,
    metrics: dict[str, float],
    promote: bool = False,
) -> None:
    """Add a model version to the registry."""
    registry = _load_registry()

    entry = {
        "version": version,
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
        for m in registry["models"]:
            if m["status"] == "champion":
                m["status"] = "archived"
        # Update champion pointer
        (MODEL_DIR / "champion.json").write_text(
            json.dumps({"version": version, "promoted_at": entry["promoted_at"]}, indent=2)
        )

    registry["models"].append(entry)
    _save_registry(registry)
    logger.info("model.registered", version=version, status=entry["status"])


# ──────────────────────────────────────────────────────────────────────
# Experiment Tracker
# ──────────────────────────────────────────────────────────────────────


class ExperimentTracker:
    """
    Context manager for MLflow experiment tracking.

    Falls back to local JSON logging if MLflow is unavailable.
    """

    def __init__(self, experiment_name: str = EXPERIMENT_NAME):
        self.experiment_name = experiment_name
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

            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = REPORTS_DIR / "feature_importance.json"
            out_path.write_text(json.dumps(importance, indent=2))
            self.log_artifact(out_path)
            return out_path

        except Exception as e:
            logger.warning("feature_importance.failed", error=str(e))
            return None

    def _save_local_log(self) -> None:
        """Save run log to local JSON as fallback."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = REPORTS_DIR / f"run_{timestamp}.json"
        self.local_log["timestamp"] = timestamp
        self.local_log["experiment"] = self.experiment_name
        if self.run:
            self.local_log["mlflow_run_id"] = self.run.info.run_id
        log_path.write_text(json.dumps(self.local_log, indent=2, default=str))
        logger.info("experiment.local_log_saved", path=str(log_path))
