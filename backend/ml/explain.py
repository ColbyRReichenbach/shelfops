"""
Model Explainability — SHAP-based explanations for demand forecasts.

Generates:
  1. Global SHAP summary plot (top 20 features)
  2. Feature importance JSON (machine-readable)
  3. Sample local explanations (waterfall plots for 5 representative predictions)

All outputs saved to reports/ and logged as MLflow artifacts.

Usage:
    from ml.explain import generate_explanations
    generate_explanations(model, X_test, feature_cols, version="v1")
"""

from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

REPORTS_DIR = Path(__file__).parent.parent / "reports"
MODELS_DIR = Path(__file__).parent.parent / "models"


def generate_explanations(
    model: Any,
    X_test: "np.ndarray | Any",
    feature_cols: list[str],
    version: str = "latest",
    n_samples: int = 5,
    max_display: int = 20,
) -> dict[str, Path]:
    """
    Generate SHAP-based model explanations.

    Args:
        model: Trained XGBoost or sklearn-compatible model.
        X_test: Test features (numpy array or DataFrame).
        feature_cols: Feature column names.
        version: Model version for output directory.
        n_samples: Number of local explanation samples.
        max_display: Features to show in summary plot.

    Returns:
        Dict of artifact paths: {
            "shap_summary": Path,
            "feature_importance": Path,
            "local_explanations": [Path, ...],
        }
    """
    try:
        import shap
        import matplotlib
        matplotlib.use("Agg")  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("shap or matplotlib not installed — skipping explanations")
        return {}

    import json
    import pandas as pd

    # Output directories
    version_dir = MODELS_DIR / version
    version_dir.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, Any] = {}

    # ── 1. Compute SHAP values ────────────────────────────────────────
    logger.info("shap.computing", n_samples=len(X_test), n_features=len(feature_cols))

    # Use TreeExplainer for XGBoost, KernelExplainer as fallback
    if hasattr(model, "get_booster"):
        explainer = shap.TreeExplainer(model)
    else:
        # Use a subsample for KernelExplainer (slow on full dataset)
        background = shap.sample(X_test, min(100, len(X_test)))
        explainer = shap.KernelExplainer(model.predict, background)

    # Compute on test set (cap at 5000 for performance)
    X_explain = X_test[:5000] if len(X_test) > 5000 else X_test
    shap_values = explainer.shap_values(X_explain)

    # ── 2. Global SHAP summary plot ───────────────────────────────────
    try:
        fig, ax = plt.subplots(figsize=(12, 8))

        if isinstance(X_explain, np.ndarray):
            X_df = pd.DataFrame(X_explain, columns=feature_cols)
        else:
            X_df = X_explain

        shap.summary_plot(
            shap_values,
            X_df,
            max_display=max_display,
            show=False,
            plot_size=(12, 8),
        )
        plt.title(f"SHAP Feature Importance — Model {version}", fontsize=14)
        plt.tight_layout()

        summary_path = version_dir / "shap_summary.png"
        plt.savefig(summary_path, dpi=150, bbox_inches="tight")
        plt.close()
        artifacts["shap_summary"] = summary_path
        logger.info("shap.summary_plot_saved", path=str(summary_path))

    except Exception as e:
        logger.warning("shap.summary_plot_failed", error=str(e))

    # ── 3. Feature importance JSON ────────────────────────────────────
    try:
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        importance = dict(
            sorted(
                zip(feature_cols, mean_abs_shap.tolist()),
                key=lambda x: x[1],
                reverse=True,
            )
        )

        importance_path = version_dir / "feature_importance.json"
        importance_path.write_text(json.dumps(importance, indent=2))
        artifacts["feature_importance"] = importance_path

        # Also save to reports/ for easy access
        (REPORTS_DIR / "feature_importance.json").write_text(
            json.dumps(importance, indent=2)
        )
        logger.info(
            "shap.feature_importance_saved",
            top_3=list(importance.keys())[:3],
        )

    except Exception as e:
        logger.warning("shap.feature_importance_failed", error=str(e))

    # ── 4. Local explanations (waterfall plots) ───────────────────────
    try:
        local_paths = []
        # Pick representative samples: min, median, max predictions
        predictions = model.predict(X_explain)
        indices = _select_representative_indices(predictions, n_samples)

        for i, idx in enumerate(indices):
            fig, ax = plt.subplots(figsize=(10, 6))
            shap.waterfall_plot(
                shap.Explanation(
                    values=shap_values[idx],
                    base_values=explainer.expected_value
                    if isinstance(explainer.expected_value, float)
                    else explainer.expected_value[0],
                    data=X_explain[idx] if isinstance(X_explain, np.ndarray) else X_explain.iloc[idx].values,
                    feature_names=feature_cols,
                ),
                max_display=12,
                show=False,
            )
            plt.title(f"Local Explanation — Sample {i+1} (pred={predictions[idx]:.1f})")
            plt.tight_layout()

            local_path = version_dir / f"shap_local_{i+1}.png"
            plt.savefig(local_path, dpi=150, bbox_inches="tight")
            plt.close()
            local_paths.append(local_path)

        artifacts["local_explanations"] = local_paths
        logger.info("shap.local_explanations_saved", count=len(local_paths))

    except Exception as e:
        logger.warning("shap.local_explanations_failed", error=str(e))

    return artifacts


def _select_representative_indices(
    predictions: np.ndarray, n: int = 5
) -> list[int]:
    """Select indices for min, 25th, median, 75th, max predictions."""
    if len(predictions) < n:
        return list(range(len(predictions)))

    percentiles = [0, 25, 50, 75, 100][:n]
    target_values = np.percentile(predictions, percentiles)
    indices = []
    for target in target_values:
        idx = int(np.argmin(np.abs(predictions - target)))
        if idx not in indices:
            indices.append(idx)
        else:
            # Find next closest that isn't already selected
            diffs = np.abs(predictions - target)
            sorted_idx = np.argsort(diffs)
            for si in sorted_idx:
                if int(si) not in indices:
                    indices.append(int(si))
                    break

    return indices[:n]
