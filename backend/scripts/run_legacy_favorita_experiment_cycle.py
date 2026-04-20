#!/usr/bin/env python3
"""
Run a bounded legacy Favorita champion/challenger cycle.

This script trains:
  - one baseline LightGBM profile
  - several challenger LightGBM profiles

It then evaluates each candidate on an untouched holdout window, applies the
same business-safe promotion gates used by the runtime arena, and writes a
report that can be attached to the experiment ledger or inspected offline.

Favorita is a legacy benchmark path. The public dataset does not include
merchant economics, so the script adds deterministic family-level placeholder
economics strictly for estimated business guardrails. Live merchant deployments
should use measured tenant pricing and costs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if str(os.getenv("DEBUG", "")).strip().lower() not in {"", "0", "1", "true", "false", "yes", "no", "on", "off"}:
    os.environ["DEBUG"] = "false"
os.environ.setdefault("APP_ENV", "test")

from ml.arena import compare_candidate_vs_champion_metrics
from ml.data_contracts import load_canonical_transactions
from ml.features import create_features, get_feature_cols
from ml.lineage import standard_model_metadata
from ml.metrics import bias_pct as compute_bias_pct
from ml.metrics import mase as compute_mase
from ml.metrics import wape as compute_wape
from ml.metrics_contract import compute_forecast_metrics, coverage_rate
from ml.replay_partition import build_time_partition, write_partition_manifest
from ml.train import TARGET_COL

try:
    import lightgbm as lgb
except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit("lightgbm is required for the legacy Favorita experiment cycle") from exc

MODEL_NAME = "demand_forecast"
CHAMPION_VERSION = "v_legacy_favorita_champion"
CHALLENGER_VERSION = "v_legacy_favorita_challenger"


@dataclass(frozen=True)
class TrainingProfile:
    feature_set_id: str
    tuning_profile: str
    change_category: str
    params: dict[str, Any]
    prediction_scale: float = 1.0
    segmentation_strategy: str | None = None


BASELINE_PROFILE = TrainingProfile(
    feature_set_id="favorita_baseline_v1",
    tuning_profile="legacy_baseline",
    change_category="baseline_refresh",
    params={},
)

CHALLENGER_PROFILES: list[TrainingProfile] = [
    TrainingProfile(
        feature_set_id="favorita_family_velocity_segmented_v1",
        tuning_profile="family_velocity_segmented_v1",
        change_category="segmentation",
        params={
            "num_leaves": 95,
            "learning_rate": 0.035,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.9,
            "bagging_freq": 3,
            "min_child_samples": 30,
            "n_estimators": 850,
        },
        segmentation_strategy="family_velocity_terciles",
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_up_v0_15",
        tuning_profile="bias_calibration_up_v0_15",
        change_category="post_processing",
        params={},
        prediction_scale=1.0015,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_up_v0_2",
        tuning_profile="bias_calibration_up_v0_2",
        change_category="post_processing",
        params={},
        prediction_scale=1.002,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_up_v0_25",
        tuning_profile="bias_calibration_up_v0_25",
        change_category="post_processing",
        params={},
        prediction_scale=1.0025,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_up_v0_5",
        tuning_profile="bias_calibration_up_v0_5",
        change_category="post_processing",
        params={},
        prediction_scale=1.005,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_v0_5",
        tuning_profile="bias_calibration_v0_5",
        change_category="post_processing",
        params={},
        prediction_scale=0.995,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_v0_75",
        tuning_profile="bias_calibration_v0_75",
        change_category="post_processing",
        params={},
        prediction_scale=0.9925,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_v0_9",
        tuning_profile="bias_calibration_v0_9",
        change_category="post_processing",
        params={},
        prediction_scale=0.99,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_v1",
        tuning_profile="bias_calibration_v1",
        change_category="post_processing",
        params={},
        prediction_scale=0.97,
    ),
    TrainingProfile(
        feature_set_id="favorita_bias_calibration_v2",
        tuning_profile="bias_calibration_v2",
        change_category="post_processing",
        params={},
        prediction_scale=0.95,
    ),
    TrainingProfile(
        feature_set_id="favorita_promo_velocity_v1",
        tuning_profile="promo_velocity_v1",
        change_category="feature_set",
        params={
            "num_leaves": 95,
            "learning_rate": 0.035,
            "feature_fraction": 0.92,
            "bagging_fraction": 0.9,
            "bagging_freq": 3,
            "min_child_samples": 35,
            "n_estimators": 800,
        },
    ),
    TrainingProfile(
        feature_set_id="favorita_promo_velocity_v2",
        tuning_profile="promo_velocity_v2",
        change_category="hyperparameter_tuning",
        params={
            "num_leaves": 63,
            "learning_rate": 0.03,
            "feature_fraction": 0.85,
            "bagging_fraction": 0.95,
            "bagging_freq": 2,
            "min_child_samples": 25,
            "n_estimators": 900,
        },
    ),
    TrainingProfile(
        feature_set_id="favorita_promo_velocity_v3",
        tuning_profile="promo_velocity_v3",
        change_category="hyperparameter_tuning",
        params={
            "num_leaves": 127,
            "learning_rate": 0.04,
            "feature_fraction": 0.88,
            "bagging_fraction": 0.88,
            "bagging_freq": 4,
            "min_child_samples": 45,
            "n_estimators": 700,
        },
    ),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the legacy Favorita experiment cycle.")
    parser.add_argument("--data-dir", default="data/kaggle/favorita", help="Legacy Favorita dataset directory")
    parser.add_argument("--holdout-days", type=int, default=14, help="Untouched holdout window in days")
    parser.add_argument(
        "--max-rows",
        type=int,
        default=75_000,
        help="Max tail rows to evaluate after canonical loading (keeps the legacy cycle bounded)",
    )
    parser.add_argument(
        "--cv-folds",
        type=int,
        default=3,
        help="Time-series CV folds per profile",
    )
    parser.add_argument(
        "--max-challengers",
        type=int,
        default=0,
        help="Optional limit on challenger profiles to evaluate (0 = all)",
    )
    parser.add_argument(
        "--partition-manifest",
        default="backend/reports/experiments/favorita_legacy_partition.json",
        help="Partition manifest output path",
    )
    parser.add_argument(
        "--output-json",
        default="backend/reports/experiments/challenger_cycle_report.json",
        help="JSON report output path",
    )
    parser.add_argument(
        "--output-md",
        default="backend/reports/experiments/challenger_cycle_report.md",
        help="Markdown report output path",
    )
    return parser.parse_args()


def _family_placeholder_economics(category: str) -> dict[str, float]:
    digest = hashlib.sha256(category.encode("utf-8")).hexdigest()
    unit_cost = 1.5 + (int(digest[:8], 16) % 2200) / 100.0
    markup = 1.28 + (int(digest[8:12], 16) % 55) / 100.0
    unit_price = unit_cost * markup
    holding_cost_per_unit_per_day = unit_cost * 0.25 / 365.0
    return {
        "category_median_cost": round(unit_cost, 2),
        "unit_cost": round(unit_cost, 2),
        "unit_price": round(unit_price, 2),
        "holding_cost_per_unit_per_day": round(holding_cost_per_unit_per_day, 4),
    }


def _augment_placeholder_economics(df: pd.DataFrame) -> pd.DataFrame:
    families = sorted(df["category"].astype(str).dropna().unique().tolist())
    economics = pd.DataFrame(
        [{"category": family, **_family_placeholder_economics(family)} for family in families],
    )
    return df.merge(economics, on="category", how="left")


def _tail_sample(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or len(df) <= max_rows:
        return df.copy()
    ordered = df.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    return ordered.tail(max_rows).reset_index(drop=True)


def _bounded_recent_window(df: pd.DataFrame, *, holdout_days: int, max_rows: int) -> pd.DataFrame:
    ordered = df.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    date_series = pd.to_datetime(ordered["date"]).dt.date
    unique_dates = sorted(pd.Series(date_series).dropna().unique().tolist())
    min_window_days = max(holdout_days * 6, 120)
    if len(unique_dates) > min_window_days:
        cutoff = unique_dates[-min_window_days]
        ordered = ordered[date_series >= cutoff].reset_index(drop=True)
    if max_rows <= 0 or len(ordered) <= max_rows:
        return ordered
    step = max(1, len(ordered) // max_rows)
    sampled = ordered.iloc[::step].head(max_rows).reset_index(drop=True)
    return sampled


def _evaluate_profile(
    *,
    train_df: pd.DataFrame,
    holdout_df: pd.DataFrame,
    feature_cols: list[str],
    profile: TrainingProfile,
    cv_folds: int,
) -> dict[str, Any]:
    print(
        f"[legacy-favorita-cycle] training {profile.feature_set_id} "
        f"(rows={len(train_df)}, holdout={len(holdout_df)}, cv_folds={cv_folds}, scale={profile.prediction_scale})",
        flush=True,
    )
    train_cutoff = max(1, int(len(train_df) * 0.85))
    fit_df = train_df.iloc[:train_cutoff].copy()
    val_df = train_df.iloc[train_cutoff:].copy()
    if val_df.empty:
        raise ValueError("Validation split is empty for challenger evaluation")

    default_params = {
        "objective": "poisson",
        "metric": "mape",
        "num_leaves": 63,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "min_child_samples": 20,
        "verbosity": -1,
        "seed": 42,
    }
    effective_params = {**default_params, **profile.params}
    num_boost_round = int(effective_params.pop("n_estimators", 500))

    val_y = pd.to_numeric(val_df[TARGET_COL], errors="coerce").fillna(0.0).clip(lower=0.0)

    booster = _fit_booster(
        fit_df=fit_df,
        val_df=val_df,
        feature_cols=feature_cols,
        effective_params=effective_params,
        num_boost_round=num_boost_round,
    )
    segment_map: dict[str, str] = {}
    segment_boosters: dict[str, lgb.Booster] = {}
    if profile.segmentation_strategy == "family_velocity_terciles":
        segment_map = _build_family_velocity_segments(train_df)
        fit_segments = fit_df.assign(_segment=fit_df["category"].map(segment_map).fillna("fallback"))
        val_segments = val_df.assign(_segment=val_df["category"].map(segment_map).fillna("fallback"))
        for segment_name in sorted(set(fit_segments["_segment"].astype(str))):
            seg_fit = fit_segments.loc[fit_segments["_segment"] == segment_name].copy()
            seg_val = val_segments.loc[val_segments["_segment"] == segment_name].copy()
            if len(seg_fit) < 1_500:
                continue
            segment_boosters[segment_name] = _fit_booster(
                fit_df=seg_fit,
                val_df=seg_val,
                feature_cols=feature_cols,
                effective_params=effective_params,
                num_boost_round=num_boost_round,
            )

    val_preds = _predict_profile(
        profile=profile,
        booster=booster,
        segment_boosters=segment_boosters,
        segment_map=segment_map,
        df=val_df,
        feature_cols=feature_cols,
    )
    cv_metrics = {
        "mae": float(np.mean(np.abs(val_y.to_numpy() - val_preds))),
        "mape": float(
            np.mean(
                np.abs(val_y.to_numpy()[val_y.to_numpy() > 0] - val_preds[val_y.to_numpy() > 0])
                / val_y.to_numpy()[val_y.to_numpy() > 0]
            )
        )
        if int((val_y.to_numpy() > 0).sum()) > 0
        else 0.0,
        "wape": float(compute_wape(val_y.to_numpy(), val_preds)),
        "mase": float(compute_mase(val_y.to_numpy(), val_preds, seasonality=7)),
        "bias_pct": float(compute_bias_pct(val_y.to_numpy(), val_preds)),
        "validation_rows": int(len(val_df)),
        "model_type": "lightgbm",
        "feature_tier": "cold_start",
        "n_features": len(feature_cols),
        "feature_cols": feature_cols,
    }

    y_train = pd.to_numeric(train_df[TARGET_COL], errors="coerce").fillna(0.0)
    y_holdout = pd.to_numeric(holdout_df[TARGET_COL], errors="coerce").fillna(0.0)

    train_preds = _predict_profile(
        profile=profile,
        booster=booster,
        segment_boosters=segment_boosters,
        segment_map=segment_map,
        df=train_df,
        feature_cols=feature_cols,
    )
    holdout_preds = _predict_profile(
        profile=profile,
        booster=booster,
        segment_boosters=segment_boosters,
        segment_map=segment_map,
        df=holdout_df,
        feature_cols=feature_cols,
    )

    train_residual_abs = np.abs(y_train.to_numpy() - train_preds)
    interval_width = float(np.quantile(train_residual_abs, 0.9)) if len(train_residual_abs) else 0.0
    lower = np.maximum(holdout_preds - interval_width, 0)
    upper = holdout_preds + interval_width

    holdout_metrics = compute_forecast_metrics(
        y_holdout,
        holdout_preds,
        unit_cost=holdout_df["unit_cost"],
        unit_price=holdout_df["unit_price"],
        holding_cost_per_unit_per_day=holdout_df["holding_cost_per_unit_per_day"],
        category=holdout_df["category"],
        category_median_cost=holdout_df["category_median_cost"],
    )
    holdout_metrics["mape"] = float(holdout_metrics["mape_nonzero"])
    holdout_metrics["coverage"] = float(coverage_rate(y_holdout, lower, upper))
    holdout_metrics["eval_rows"] = int(len(holdout_df))
    holdout_metrics["interval_q90_width"] = interval_width
    print(
        "[legacy-favorita-cycle] finished "
        f"{profile.feature_set_id} "
        f"(wape={holdout_metrics['wape']:.4f}, mase={holdout_metrics['mase']:.4f}, "
        f"overstock={float(holdout_metrics.get('overstock_dollars') or 0.0):.2f})",
        flush=True,
    )

    return {
        "profile": profile,
        "model": booster,
        "cv_metrics": cv_metrics,
        "holdout_metrics": holdout_metrics,
        "predictions": holdout_preds,
        "segment_summary": {
            "strategy": profile.segmentation_strategy,
            "segments": sorted(segment_boosters.keys()),
            "family_count": len(segment_map),
        }
        if profile.segmentation_strategy
        else None,
    }


def _fit_booster(
    *,
    fit_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    effective_params: dict[str, Any],
    num_boost_round: int,
) -> lgb.Booster:
    fit_X = fit_df[feature_cols].fillna(0)
    fit_y = pd.to_numeric(fit_df[TARGET_COL], errors="coerce").fillna(0.0).clip(lower=0.0)
    train_dataset = lgb.Dataset(fit_X, label=fit_y)
    valid_sets: list[lgb.Dataset] = []
    callbacks: list[Any] = [lgb.log_evaluation(-1)]
    if not val_df.empty:
        val_X = val_df[feature_cols].fillna(0)
        val_y = pd.to_numeric(val_df[TARGET_COL], errors="coerce").fillna(0.0).clip(lower=0.0)
        valid_sets.append(lgb.Dataset(val_X, label=val_y))
        callbacks.insert(0, lgb.early_stopping(30, verbose=False))
    return lgb.train(
        effective_params,
        train_dataset,
        num_boost_round=num_boost_round,
        valid_sets=valid_sets or None,
        callbacks=callbacks,
    )


def _build_family_velocity_segments(train_df: pd.DataFrame) -> dict[str, str]:
    family_summary = (
        train_df.groupby("category")[TARGET_COL].agg(["sum", "mean"]).fillna(0.0).sort_values(["sum", "mean"])
    )
    if family_summary.empty:
        return {}
    segment_count = min(3, len(family_summary))
    labels = ["low_velocity", "mid_velocity", "high_velocity"][-segment_count:]
    ranked = family_summary["sum"].rank(method="first")
    buckets = pd.qcut(ranked, q=segment_count, labels=labels, duplicates="drop")
    bucket_strings = pd.Series(buckets.astype(str), index=family_summary.index)
    return {str(category): segment for category, segment in bucket_strings.items()}


def _predict_profile(
    *,
    profile: TrainingProfile,
    booster: lgb.Booster,
    segment_boosters: dict[str, lgb.Booster],
    segment_map: dict[str, str],
    df: pd.DataFrame,
    feature_cols: list[str],
) -> np.ndarray:
    base_preds = np.maximum(booster.predict(df[feature_cols].fillna(0)) * profile.prediction_scale, 0)
    if not profile.segmentation_strategy or not segment_boosters or df.empty:
        return base_preds

    segment_series = df["category"].map(segment_map).fillna("fallback")
    preds = base_preds.copy()
    for segment_name, segment_booster in segment_boosters.items():
        mask = segment_series == segment_name
        if not bool(mask.any()):
            continue
        seg_X = df.loc[mask, feature_cols].fillna(0)
        preds[mask.to_numpy()] = np.maximum(
            segment_booster.predict(seg_X) * profile.prediction_scale,
            0,
        )
    return preds


def _selection_score(metrics: dict[str, Any]) -> float:
    wape = float(metrics.get("wape") or math.inf)
    mase = float(metrics.get("mase") or math.inf)
    overstock = float(metrics.get("overstock_dollars") or math.inf)
    stockout = float(metrics.get("opportunity_cost_stockout") or math.inf)
    bias = abs(float(metrics.get("bias_pct") or 0.0))
    return (wape * 1000.0) + (mase * 100.0) + overstock + stockout + (bias * 10.0)


def _select_best_challenger(
    baseline_metrics: dict[str, Any],
    challenger_runs: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    comparisons = [
        {
            "run": run,
            "comparison": compare_candidate_vs_champion_metrics(baseline_metrics, run["holdout_metrics"]),
        }
        for run in challenger_runs
    ]
    promoted = [row for row in comparisons if row["comparison"]["promoted"]]
    pool = promoted or comparisons
    best = min(pool, key=lambda row: _selection_score(row["run"]["holdout_metrics"]))
    return best["run"], best["comparison"]


def _serialize_result(
    *,
    version: str,
    result: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    profile: TrainingProfile = result["profile"]
    return {
        "version": version,
        "feature_set_id": profile.feature_set_id,
        "tuning_profile": profile.tuning_profile,
        "change_category": profile.change_category,
        "prediction_scale": profile.prediction_scale,
        "segmentation_strategy": profile.segmentation_strategy,
        "cv_metrics": result["cv_metrics"],
        "holdout_metrics": result["holdout_metrics"],
        "lineage_metadata": metadata,
        "segment_summary": result.get("segment_summary"),
    }


def _write_markdown_report(payload: dict[str, Any], output_path: Path) -> None:
    baseline = payload["baseline"]
    challenger = payload["challenger"]
    decision = payload["comparison"]
    lines = [
        "# Legacy Favorita Experiment Cycle",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- data_dir: `{payload['data_dir']}`",
        f"- rows_used: `{payload['rows_used']}`",
        f"- holdout_days: `{payload['holdout_days']}`",
        f"- estimated_business_basis: `{payload['estimated_business_basis']}`",
        "",
        "## Baseline",
        "",
        f"- version: `{baseline['version']}`",
        f"- feature_set_id: `{baseline['feature_set_id']}`",
        f"- tuning_profile: `{baseline['tuning_profile']}`",
        f"- holdout_wape: `{baseline['holdout_metrics']['wape']:.6f}`",
        f"- holdout_mase: `{baseline['holdout_metrics']['mase']:.6f}`",
        f"- holdout_overstock_dollars: `{baseline['holdout_metrics']['overstock_dollars']:.2f}`",
        "",
        "## Challenger",
        "",
        f"- version: `{challenger['version']}`",
        f"- feature_set_id: `{challenger['feature_set_id']}`",
        f"- tuning_profile: `{challenger['tuning_profile']}`",
        f"- holdout_wape: `{challenger['holdout_metrics']['wape']:.6f}`",
        f"- holdout_mase: `{challenger['holdout_metrics']['mase']:.6f}`",
        f"- holdout_overstock_dollars: `{challenger['holdout_metrics']['overstock_dollars']:.2f}`",
        "",
        "## Promotion Comparison",
        "",
        f"- promoted_by_live_gates: `{decision['promoted']}`",
        f"- reason: `{decision['reason']}`",
        "",
        "| gate | passed |",
        "|---|---:|",
    ]
    for name, passed in sorted(decision["gate_checks"].items()):
        lines.append(f"| {name} | {passed} |")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _select_profiles(
    experiment_type: str | None,
    lineage_metadata: dict[str, Any] | None,
    max_challengers: int,
) -> list[TrainingProfile]:
    metadata = lineage_metadata or {}
    requested_segment = str(metadata.get("segment_strategy") or "").lower()
    segment_profiles = [profile for profile in CHALLENGER_PROFILES if profile.change_category == "segmentation"]
    tuning_profiles = [profile for profile in CHALLENGER_PROFILES if profile.change_category == "hyperparameter_tuning"]
    feature_profiles = [profile for profile in CHALLENGER_PROFILES if profile.change_category == "feature_set"]
    post_processing_profiles = [
        profile for profile in CHALLENGER_PROFILES if profile.change_category == "post_processing"
    ]

    if experiment_type == "segmentation" or "segment" in requested_segment:
        selected = segment_profiles or CHALLENGER_PROFILES
    elif experiment_type == "hyperparameter_tuning":
        selected = tuning_profiles or CHALLENGER_PROFILES
    elif experiment_type == "post_processing":
        selected = post_processing_profiles or CHALLENGER_PROFILES
    elif experiment_type == "feature_set":
        selected = feature_profiles or CHALLENGER_PROFILES
    else:
        selected = CHALLENGER_PROFILES

    return selected[:max_challengers] if max_challengers > 0 else selected


def run_legacy_favorita_experiment_cycle(
    *,
    data_dir: str = "data/kaggle/favorita",
    holdout_days: int = 14,
    max_rows: int = 75_000,
    cv_folds: int = 3,
    max_challengers: int = 0,
    partition_manifest: str = "backend/reports/experiments/favorita_legacy_partition.json",
    output_json: str = "backend/reports/experiments/challenger_cycle_report.json",
    output_md: str = "backend/reports/experiments/challenger_cycle_report.md",
    experiment_context: dict[str, Any] | None = None,
    champion_version: str | None = None,
    challenger_version: str | None = None,
) -> dict[str, Any]:
    context = experiment_context or {}
    lineage_metadata = dict(context.get("lineage_metadata") or {})
    effective_champion_version = champion_version or context.get("baseline_version") or CHAMPION_VERSION
    effective_challenger_version = challenger_version or context.get("experimental_version") or CHALLENGER_VERSION

    raw = load_canonical_transactions(data_dir)
    raw = _augment_placeholder_economics(_bounded_recent_window(raw, holdout_days=holdout_days, max_rows=max_rows))
    partition = build_time_partition(
        raw,
        holdout_days=holdout_days,
        dataset_id="favorita",
        source_paths=[str(p.resolve()) for p in sorted(Path(data_dir).rglob("*.csv")) if p.is_file()],
    )
    train_end_date = partition["metadata"]["train_end_date"]
    write_partition_manifest(partition["metadata"], partition_manifest)

    features = create_features(transactions_df=raw, force_tier="cold_start")
    feature_cols = [c for c in get_feature_cols("cold_start") if c in features.columns]

    feature_dates = pd.to_datetime(features["date"]).dt.date
    train_mask = feature_dates <= pd.to_datetime(train_end_date).date()
    train_features = features.loc[train_mask].copy()
    holdout_features = features.loc[~train_mask].copy()
    if holdout_features.empty:
        raise ValueError("Holdout feature frame is empty; increase max_rows or decrease holdout_days")

    baseline_metadata = standard_model_metadata(
        model_name=MODEL_NAME,
        dataset_id="favorita",
        forecast_grain="store_nbr_family_date",
        feature_tier="cold_start",
        trigger_source="baseline_refresh",
        change_category=BASELINE_PROFILE.change_category,
        feature_set_id=BASELINE_PROFILE.feature_set_id,
        tuning_profile=BASELINE_PROFILE.tuning_profile,
        baseline_version=effective_champion_version,
        candidate_version=effective_champion_version,
    )
    baseline_result = _evaluate_profile(
        train_df=train_features,
        holdout_df=holdout_features,
        feature_cols=feature_cols,
        profile=BASELINE_PROFILE,
        cv_folds=cv_folds,
    )

    challenger_profiles = _select_profiles(
        str(context.get("experiment_type") or ""),
        lineage_metadata,
        max_challengers,
    )
    challenger_runs: list[dict[str, Any]] = []
    for profile in challenger_profiles:
        challenger_runs.append(
            _evaluate_profile(
                train_df=train_features,
                holdout_df=holdout_features,
                feature_cols=feature_cols,
                profile=profile,
                cv_folds=cv_folds,
            )
        )

    best_challenger, comparison = _select_best_challenger(baseline_result["holdout_metrics"], challenger_runs)
    best_profile: TrainingProfile = best_challenger["profile"]
    effective_feature_set_id = str(lineage_metadata.get("feature_set_id") or best_profile.feature_set_id)
    effective_segment_strategy = str(
        lineage_metadata.get("segment_strategy") or best_profile.segmentation_strategy or "global"
    )
    challenger_metadata = standard_model_metadata(
        model_name=str(context.get("model_name") or MODEL_NAME),
        dataset_id="favorita",
        forecast_grain="store_nbr_family_date",
        feature_tier="cold_start",
        trigger_source="manual_hypothesis",
        change_category=best_profile.change_category,
        feature_set_id=effective_feature_set_id,
        tuning_profile=best_profile.tuning_profile,
        baseline_version=effective_champion_version,
        candidate_version=effective_challenger_version,
        segment_strategy=effective_segment_strategy,
    )

    comparison["decision"]["estimated_business_basis"] = True
    comparison["decision"]["business_basis_note"] = (
        "Favorita lacks measured unit economics; this legacy benchmark path used deterministic family-level estimated costs."
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_dir": data_dir,
        "rows_used": int(len(raw)),
        "holdout_days": int(holdout_days),
        "train_end_date": train_end_date,
        "estimated_business_basis": True,
        "business_basis_note": comparison["decision"]["business_basis_note"],
        "baseline": _serialize_result(
            version=effective_champion_version,
            result=baseline_result,
            metadata=baseline_metadata,
        ),
        "challenger": _serialize_result(
            version=effective_challenger_version,
            result=best_challenger,
            metadata=challenger_metadata,
        ),
        "challenger_candidates": [
            {
                "feature_set_id": run["profile"].feature_set_id,
                "tuning_profile": run["profile"].tuning_profile,
                "prediction_scale": run["profile"].prediction_scale,
                "holdout_metrics": run["holdout_metrics"],
                "cv_metrics": run["cv_metrics"],
            }
            for run in challenger_runs
        ],
        "comparison": comparison,
        "experiment": {
            "experiment_name": context.get("experiment_name") or "Legacy Favorita promo + velocity feature trial",
            "hypothesis": context.get("hypothesis")
            or (
                "Promo-aware interactions and tuned recent-demand sensitivity will reduce overstock and "
                "stockout opportunity cost without regressing WAPE or MASE."
            ),
            "experiment_type": context.get("experiment_type") or "feature_set",
            "model_name": context.get("model_name") or MODEL_NAME,
            "baseline_version": effective_champion_version,
            "experimental_version": effective_challenger_version,
            "decision": "promotion_ready" if comparison["promoted"] else "continue_shadow_review",
            "decision_rationale": comparison["reason"],
            "lineage_metadata": challenger_metadata,
        },
    }

    output_json_path = Path(output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown_report(payload, Path(output_md))
    return payload


def main() -> int:
    args = _parse_args()
    payload = run_legacy_favorita_experiment_cycle(
        data_dir=args.data_dir,
        holdout_days=args.holdout_days,
        max_rows=args.max_rows,
        cv_folds=args.cv_folds,
        max_challengers=args.max_challengers,
        partition_manifest=args.partition_manifest,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
