#!/usr/bin/env python3
"""
Time-travel replay simulation for ShelfOps.

Runs a deterministic daily replay over an untouched holdout window and emits
artifacts for forecast quality, retrain triggers, HITL actions, and model
strategy decisions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add backend to path so imports work when script is run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from db.models import (
    Customer,
    DemandForecast,
    ForecastAccuracy,
    ModelExperiment,
    ModelRetrainingLog,
    ModelVersion,
    Product,
    Store,
)
from db.session import Base
from ml.data_contracts import load_canonical_transactions
from ml.features import create_features, get_feature_cols
from ml.metrics_contract import compute_forecast_metrics
from ml.replay_hitl_policy import decide_model_promotion, decide_po_action
from ml.replay_partition import build_time_partition, write_partition_manifest
from ml.train import train_lstm, train_xgboost


@dataclass
class ReplayThresholds:
    mape_nonzero_max: float = 0.22
    stockout_miss_rate_max: float = 0.08
    overstock_rate_max: float = 0.55


class ReplayDbAdapter:
    """Persist replay output into live MLOps tables for non-dry-run execution."""

    def __init__(self, *, customer_id: str, enabled: bool, max_rows_per_day: int):
        self.enabled = enabled
        self.max_rows_per_day = max(1, int(max_rows_per_day))
        self.customer_id_raw = customer_id
        self.customer_uuid: uuid.UUID | None = None
        self._namespace: uuid.UUID | None = None
        self._engine = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

        if not enabled:
            return

        try:
            self.customer_uuid = uuid.UUID(customer_id)
        except ValueError as exc:
            raise ValueError(f"Invalid customer UUID for DB replay mode: {customer_id}") from exc

        self._namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"shelfops-replay::{customer_id}")

    def _ensure_enabled(self) -> tuple[uuid.UUID, uuid.UUID]:
        if not self.enabled or self.customer_uuid is None or self._namespace is None:
            raise RuntimeError("ReplayDbAdapter is not enabled")
        return self.customer_uuid, self._namespace

    def _ensure_session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("ReplayDbAdapter session factory not initialized")
        return self._session_factory

    async def open(self) -> None:
        if not self.enabled:
            return
        settings = get_settings()
        self._engine = create_async_engine(settings.database_url)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._session_factory = async_sessionmaker(self._engine, class_=AsyncSession, expire_on_commit=False)
        await self._ensure_customer()

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()

    async def _ensure_customer(self) -> None:
        customer_uuid, _ = self._ensure_enabled()
        session_factory = self._ensure_session_factory()
        async with session_factory() as db:
            existing = await db.execute(
                select(Customer.customer_id).where(Customer.customer_id == customer_uuid).limit(1)
            )
            if existing.scalar_one_or_none() is not None:
                return
            db.add(
                Customer(
                    customer_id=customer_uuid,
                    name="Replay Customer",
                    email=f"replay-{customer_uuid}@shelfops.local",
                    plan="professional",
                    status="active",
                )
            )
            await db.commit()

    def _store_uuid(self, raw_store_id: Any) -> uuid.UUID:
        _, namespace = self._ensure_enabled()
        return uuid.uuid5(namespace, f"store::{raw_store_id}")

    def _product_uuid(self, raw_product_id: Any) -> uuid.UUID:
        _, namespace = self._ensure_enabled()
        return uuid.uuid5(namespace, f"product::{raw_product_id}")

    def _limit_day_rows(self, day_rows: pd.DataFrame, preds: np.ndarray) -> tuple[pd.DataFrame, np.ndarray]:
        if len(day_rows) <= self.max_rows_per_day:
            return day_rows.reset_index(drop=True), preds
        step = max(1, len(day_rows) // self.max_rows_per_day)
        idx = np.arange(0, len(day_rows), step)[: self.max_rows_per_day]
        return day_rows.iloc[idx].reset_index(drop=True), preds[idx]

    async def _ensure_reference_rows(self, day_rows: pd.DataFrame) -> None:
        customer_uuid, _ = self._ensure_enabled()
        session_factory = self._ensure_session_factory()

        store_values = [str(v) for v in day_rows["store_id"].astype(str).tolist()]
        product_values = [str(v) for v in day_rows["product_id"].astype(str).tolist()]
        store_pairs = {raw: self._store_uuid(raw) for raw in store_values}
        product_pairs = {raw: self._product_uuid(raw) for raw in product_values}

        async with session_factory() as db:
            existing_store_ids = {
                row[0]
                for row in (
                    await db.execute(
                        select(Store.store_id).where(
                            Store.customer_id == customer_uuid,
                            Store.store_id.in_(list(store_pairs.values())),
                        )
                    )
                ).all()
            }
            missing_stores = [
                {
                    "store_id": store_uuid,
                    "customer_id": customer_uuid,
                    "name": f"Replay Store {raw}"[:255],
                    "status": "active",
                    "timezone": "UTC",
                    "cluster_tier": 1,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
                for raw, store_uuid in store_pairs.items()
                if store_uuid not in existing_store_ids
            ]
            if missing_stores:
                await db.execute(insert(Store), missing_stores)

            existing_product_ids = {
                row[0]
                for row in (
                    await db.execute(
                        select(Product.product_id).where(
                            Product.customer_id == customer_uuid,
                            Product.product_id.in_(list(product_pairs.values())),
                        )
                    )
                ).all()
            }
            category_map = (
                day_rows[["product_id", "category"]].drop_duplicates("product_id").set_index("product_id")["category"].to_dict()
                if "category" in day_rows.columns
                else {}
            )
            missing_products = []
            for raw, product_uuid in product_pairs.items():
                if product_uuid in existing_product_ids:
                    continue
                sku = f"replay-{raw}".replace(" ", "_")[:100]
                missing_products.append(
                    {
                        "product_id": product_uuid,
                        "customer_id": customer_uuid,
                        "sku": sku,
                        "name": f"Replay Product {raw}"[:255],
                        "category": str(category_map.get(raw) or "unknown")[:100],
                        "unit_cost": 1.0,
                        "unit_price": 2.0,
                        "status": "active",
                        "lifecycle_state": "active",
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
            if missing_products:
                await db.execute(insert(Product), missing_products)
            await db.commit()

    async def record_retrain_event(
        self,
        *,
        replay_date: date,
        model_version: str,
        retrain_reasons: list[str],
        train_end_date: date,
    ) -> None:
        customer_uuid, _ = self._ensure_enabled()
        session_factory = self._ensure_session_factory()

        if "drift_detected" in retrain_reasons:
            trigger = "drift"
        elif any(reason.startswith("scheduled") or reason == "initial" for reason in retrain_reasons):
            trigger = "scheduled"
        else:
            trigger = "manual"

        now = datetime.utcnow()
        async with session_factory() as db:
            existing = await db.execute(
                select(ModelVersion.model_id, ModelVersion.metrics).where(
                    ModelVersion.customer_id == customer_uuid,
                    ModelVersion.model_name == "demand_forecast",
                    ModelVersion.version == model_version,
                )
            )
            row = existing.one_or_none()
            metrics = {
                "source": "replay_simulation",
                "last_retrain_date": replay_date.isoformat(),
                "train_end_date": train_end_date.isoformat(),
                "trigger_reasons": sorted(set(retrain_reasons)),
            }
            if row:
                merged_metrics = dict(row.metrics or {})
                merged_metrics.update(metrics)
                await db.execute(
                    update(ModelVersion)
                    .where(ModelVersion.model_id == row.model_id)
                    .values(
                        status="candidate",
                        routing_weight=0.0,
                        smoke_test_passed=True,
                        metrics=merged_metrics,
                    )
                )
            else:
                await db.execute(
                    insert(ModelVersion).values(
                        customer_id=customer_uuid,
                        model_name="demand_forecast",
                        version=model_version,
                        status="candidate",
                        routing_weight=0.0,
                        promoted_at=None,
                        archived_at=None,
                        metrics=metrics,
                        smoke_test_passed=True,
                        created_at=now,
                    )
                )

            await db.execute(
                insert(ModelRetrainingLog).values(
                    customer_id=customer_uuid,
                    model_name="demand_forecast",
                    trigger_type=trigger,
                    trigger_metadata={
                        "replay_date": replay_date.isoformat(),
                        "reasons": sorted(set(retrain_reasons)),
                        "train_end_date": train_end_date.isoformat(),
                    },
                    status="completed",
                    version_produced=model_version,
                    started_at=now,
                    completed_at=now,
                )
            )
            await db.commit()

    async def persist_day_metrics(
        self,
        *,
        replay_date: date,
        day_rows: pd.DataFrame,
        preds: np.ndarray,
        model_version: str,
    ) -> tuple[int, int]:
        customer_uuid, _ = self._ensure_enabled()
        session_factory = self._ensure_session_factory()

        limited_rows, limited_preds = self._limit_day_rows(day_rows, preds)
        await self._ensure_reference_rows(limited_rows)

        forecast_rows: list[dict[str, Any]] = []
        accuracy_rows: list[dict[str, Any]] = []
        now = datetime.utcnow()
        for row, pred in zip(limited_rows.itertuples(index=False), limited_preds, strict=False):
            store_uuid = self._store_uuid(row.store_id)
            product_uuid = self._product_uuid(row.product_id)
            forecasted = float(max(pred, 0.0))
            actual = float(row.quantity)
            mae = abs(forecasted - actual)
            mape = (mae / abs(actual)) if actual else 0.0
            forecast_rows.append(
                {
                    "customer_id": customer_uuid,
                    "store_id": store_uuid,
                    "product_id": product_uuid,
                    "forecast_date": replay_date,
                    "forecasted_demand": forecasted,
                    "lower_bound": max(forecasted * 0.8, 0.0),
                    "upper_bound": forecasted * 1.2,
                    "confidence": 0.90,
                    "model_version": model_version,
                    "created_at": now,
                }
            )
            accuracy_rows.append(
                {
                    "customer_id": customer_uuid,
                    "store_id": store_uuid,
                    "product_id": product_uuid,
                    "forecast_date": replay_date,
                    "forecasted_demand": forecasted,
                    "actual_demand": actual,
                    "mae": mae,
                    "mape": mape,
                    "model_version": model_version,
                    "evaluated_at": now,
                }
            )

        async with session_factory() as db:
            await db.execute(
                delete(DemandForecast).where(
                    DemandForecast.customer_id == customer_uuid,
                    DemandForecast.model_version == model_version,
                    DemandForecast.forecast_date == replay_date,
                )
            )
            await db.execute(
                delete(ForecastAccuracy).where(
                    ForecastAccuracy.customer_id == customer_uuid,
                    ForecastAccuracy.model_version == model_version,
                    ForecastAccuracy.forecast_date == replay_date,
                )
            )
            if forecast_rows:
                await db.execute(insert(DemandForecast), forecast_rows)
            if accuracy_rows:
                await db.execute(insert(ForecastAccuracy), accuracy_rows)
            await db.commit()
        return len(forecast_rows), len(accuracy_rows)

    async def record_promotion_decision(
        self,
        *,
        model_version: str,
        decision: str,
        reason_code: str,
        gate_passed: bool,
        candidate_summary: dict[str, float],
    ) -> None:
        customer_uuid, _ = self._ensure_enabled()
        session_factory = self._ensure_session_factory()
        now = datetime.utcnow()
        approved = decision == "approve"

        async with session_factory() as db:
            existing = await db.execute(
                select(ModelVersion.model_id, ModelVersion.metrics).where(
                    ModelVersion.customer_id == customer_uuid,
                    ModelVersion.model_name == "demand_forecast",
                    ModelVersion.version == model_version,
                )
            )
            row = existing.one_or_none()
            if row:
                merged_metrics = dict(row.metrics or {})
                merged_metrics["last_replay_promotion_decision"] = {
                    "decision": decision,
                    "reason_code": reason_code,
                    "gate_passed": bool(gate_passed),
                    "decided_at": now.isoformat(),
                }
                await db.execute(
                    update(ModelVersion)
                    .where(ModelVersion.model_id == row.model_id)
                    .values(
                        status="champion" if approved else "challenger",
                        routing_weight=1.0 if approved else 0.0,
                        promoted_at=now if approved else None,
                        metrics=merged_metrics,
                    )
                )
            if approved:
                await db.execute(
                    update(ModelVersion)
                    .where(
                        ModelVersion.customer_id == customer_uuid,
                        ModelVersion.model_name == "demand_forecast",
                        ModelVersion.status == "champion",
                        ModelVersion.version != model_version,
                    )
                    .values(status="archived", archived_at=now, routing_weight=0.0)
                )

            await db.execute(
                insert(ModelExperiment).values(
                    customer_id=customer_uuid,
                    experiment_name=f"replay_promotion_{model_version}_{decision}",
                    hypothesis="Replay challenger promotion decision",
                    experiment_type="model_architecture",
                    model_name="demand_forecast",
                    baseline_version=None,
                    experimental_version=model_version,
                    status="completed" if approved else "rejected",
                    proposed_by="replay-simulation",
                    approved_by="replay-simulation" if approved else None,
                    results={
                        "decision": decision,
                        "reason_code": reason_code,
                        "gate_passed": bool(gate_passed),
                        "candidate_summary": candidate_summary,
                    },
                    decision_rationale=reason_code,
                    created_at=now,
                    approved_at=now if approved else None,
                    completed_at=now,
                )
            )
            await db.commit()


def _weighted_metric(entries: list[dict[str, Any]], key: str) -> float:
    num = 0.0
    den = 0.0
    for row in entries:
        samples = float(row.get("samples", 0) or 0)
        value = float(row.get(key, 0.0) or 0.0)
        num += value * samples
        den += samples
    return (num / den) if den else 0.0


def _evaluate_baseline_gate(summary_metrics: dict[str, float], thresholds: ReplayThresholds) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if summary_metrics.get("mape_nonzero", 0.0) > thresholds.mape_nonzero_max:
        failures.append("mape_nonzero")
    if summary_metrics.get("stockout_miss_rate", 0.0) > thresholds.stockout_miss_rate_max:
        failures.append("stockout_miss_rate")
    if summary_metrics.get("overstock_rate", 0.0) > thresholds.overstock_rate_max:
        failures.append("overstock_rate")
    if summary_metrics.get("critical_failures", 0.0) > 0:
        failures.append("critical_failures")
    return (len(failures) == 0), failures


def _promotion_gate_pass(
    *,
    candidate_metrics: dict[str, float],
    champion_metrics: dict[str, float] | None,
) -> bool:
    if champion_metrics is None:
        return True

    # Candidate non-regression gate.
    mae_ok = candidate_metrics["mae"] <= champion_metrics["mae"] * 1.02
    mape_ok = candidate_metrics["mape_nonzero"] <= champion_metrics["mape_nonzero"] * 1.02
    stockout_ok = candidate_metrics["stockout_miss_rate"] <= champion_metrics["stockout_miss_rate"] + 0.005
    overstock_ok = candidate_metrics["overstock_rate"] <= champion_metrics["overstock_rate"] + 0.005
    return bool(mae_ok and mape_ok and stockout_ok and overstock_ok)


def _limit_training_rows(df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or len(df) <= max_rows:
        return df
    return df.tail(max_rows).copy()


def _sample_holdout_for_portfolio(holdout_df: pd.DataFrame, max_rows: int) -> pd.DataFrame:
    if max_rows <= 0 or len(holdout_df) <= max_rows:
        return holdout_df
    step = max(1, len(holdout_df) // max_rows)
    sampled = holdout_df.iloc[::step].head(max_rows).copy()
    return sampled


def _compute_lstm_predictions(
    *,
    lstm_model: Any,
    feature_matrix_all: np.ndarray,
    eval_indices: np.ndarray,
    seq_len: int,
    fallback_preds: np.ndarray,
) -> np.ndarray:
    """
    Compute sequence-based LSTM predictions for evaluation rows.

    For rows without enough prior sequence context, fallback to the provided
    baseline predictions.
    """
    if lstm_model is None:
        return fallback_preds.copy()

    norm_mean = getattr(lstm_model, "_norm_mean", None)
    norm_std = getattr(lstm_model, "_norm_std", None)
    if norm_mean is None or norm_std is None:
        return fallback_preds.copy()

    x_norm = (feature_matrix_all - norm_mean) / norm_std
    preds = fallback_preds.copy()

    valid_positions: list[int] = []
    sequences: list[np.ndarray] = []
    for pos, idx in enumerate(eval_indices):
        if idx < seq_len:
            continue
        sequences.append(x_norm[idx - seq_len : idx])
        valid_positions.append(pos)

    if not sequences:
        return preds

    batch = np.stack(sequences)
    raw = lstm_model.predict(batch, verbose=0).reshape(-1)
    raw = np.maximum(raw, 0.0)
    for pos, value in zip(valid_positions, raw, strict=False):
        preds[pos] = float(value)
    return preds


def _evaluate_portfolio(
    *,
    features_df: pd.DataFrame,
    train_end_date: date,
    feature_cols: list[str],
    max_training_rows: int,
    max_eval_rows: int,
) -> dict[str, Any]:
    train_df = features_df[pd.to_datetime(features_df["date"]).dt.date <= train_end_date].copy()
    holdout_df = features_df[pd.to_datetime(features_df["date"]).dt.date > train_end_date].copy()

    train_df = _limit_training_rows(train_df, max_training_rows)
    holdout_df = _sample_holdout_for_portfolio(holdout_df, max_eval_rows)

    X_eval = holdout_df[feature_cols].fillna(0)
    y_eval = holdout_df["quantity"].astype(float)

    xgb_model, _ = train_xgboost(
        train_df,
        feature_cols=feature_cols,
        params={
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "early_stopping_rounds": 20,
            "random_state": 42,
        },
    )
    xgb_preds = np.maximum(xgb_model.predict(X_eval), 0.0)

    lstm_model = None
    lstm_seq_len = 14
    lstm_error = None
    try:
        lstm_model, lstm_metrics = train_lstm(
            train_df,
            feature_cols=feature_cols,
            sequence_length=14,
            epochs=3,
            batch_size=64,
            max_samples=min(12000, len(train_df)),
        )
        lstm_seq_len = int(lstm_metrics.get("sequence_length", 14))
    except Exception as exc:  # noqa: BLE001
        lstm_error = str(exc)

    all_matrix = features_df[feature_cols].fillna(0).values
    eval_indices = holdout_df.index.to_numpy(dtype=int)
    lstm_preds = _compute_lstm_predictions(
        lstm_model=lstm_model,
        feature_matrix_all=all_matrix,
        eval_indices=eval_indices,
        seq_len=lstm_seq_len,
        fallback_preds=xgb_preds,
    )

    candidates = []
    for xgb_weight in (1.0, 0.9, 0.8, 0.65):
        lstm_weight = round(1.0 - xgb_weight, 2)
        blend = np.maximum((xgb_weight * xgb_preds) + (lstm_weight * lstm_preds), 0.0)
        metrics = compute_forecast_metrics(y_eval, blend)
        candidates.append(
            {
                "xgboost_weight": xgb_weight,
                "lstm_weight": lstm_weight,
                "mae": float(metrics["mae"]),
                "mape_nonzero": float(metrics["mape_nonzero"]),
                "stockout_miss_rate": float(metrics["stockout_miss_rate"]),
                "overstock_rate": float(metrics["overstock_rate"]),
            }
        )

    best = min(candidates, key=lambda row: (row["mape_nonzero"], row["mae"]))
    return {
        "evaluated_rows": int(len(holdout_df)),
        "lstm_available": lstm_model is not None,
        "lstm_error": lstm_error,
        "candidates": candidates,
        "recommended": best,
    }


def _render_summary_md(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Replay Summary",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- dataset_id: `{summary['dataset_id']}`",
        f"- replay_start: `{summary['replay_start']}`",
        f"- replay_end: `{summary['replay_end']}`",
        f"- replay_days: `{summary['replay_days']}`",
        f"- retrain_count: `{summary['retrain_count']}`",
        f"- critical_failures: `{summary['critical_failures']}`",
        "",
        "## Baseline Metrics",
        "",
        f"- mae: `{summary['baseline_metrics']['mae']:.6f}`",
        f"- mape_nonzero: `{summary['baseline_metrics']['mape_nonzero']:.6f}`",
        f"- stockout_miss_rate: `{summary['baseline_metrics']['stockout_miss_rate']:.6f}`",
        f"- overstock_rate: `{summary['baseline_metrics']['overstock_rate']:.6f}`",
        f"- baseline_gate_passed: `{summary['baseline_gate_passed']}`",
        f"- baseline_gate_failures: `{summary['baseline_gate_failures']}`",
        "",
        "## HITL",
        "",
        f"- po_approve: `{summary['hitl_counts'].get('po_approve', 0)}`",
        f"- po_edit: `{summary['hitl_counts'].get('po_edit', 0)}`",
        f"- po_reject: `{summary['hitl_counts'].get('po_reject', 0)}`",
        f"- model_promote_approve: `{summary['hitl_counts'].get('model_promote_approve', 0)}`",
        f"- model_promote_reject: `{summary['hitl_counts'].get('model_promote_reject', 0)}`",
    ]

    if summary.get("portfolio"):
        portfolio = summary["portfolio"]
        lines.extend(
            [
                "",
                "## Portfolio Evaluation",
                "",
                f"- evaluated_rows: `{portfolio['evaluated_rows']}`",
                f"- lstm_available: `{portfolio['lstm_available']}`",
                f"- recommended_weights: xgb={portfolio['recommended']['xgboost_weight']}, "
                f"lstm={portfolio['recommended']['lstm_weight']}",
                f"- recommended_mape_nonzero: `{portfolio['recommended']['mape_nonzero']:.6f}`",
            ]
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_strategy_md(summary: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# Replay Model Strategy Decision",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- baseline_gate_passed: `{summary['baseline_gate_passed']}`",
        f"- baseline_gate_failures: `{summary['baseline_gate_failures']}`",
        "",
    ]

    portfolio = summary.get("portfolio")
    if not portfolio:
        lines.extend(
            [
                "## Decision",
                "",
                "- Portfolio phase not executed (baseline passed or portfolio_mode=off).",
                "- Recommended serving mode remains baseline XGBoost-first.",
            ]
        )
    else:
        lines.extend(
            [
                "## Candidate Weights",
                "",
                "| xgboost_weight | lstm_weight | mae | mape_nonzero | stockout_miss_rate | overstock_rate |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in portfolio["candidates"]:
            lines.append(
                f"| {row['xgboost_weight']:.2f} | {row['lstm_weight']:.2f} | {row['mae']:.6f} | "
                f"{row['mape_nonzero']:.6f} | {row['stockout_miss_rate']:.6f} | {row['overstock_rate']:.6f} |"
            )

        rec = portfolio["recommended"]
        lines.extend(
            [
                "",
                "## Decision",
                "",
                "- Portfolio phase executed because baseline replay gate failed.",
                f"- Recommended weights: xgb={rec['xgboost_weight']}, lstm={rec['lstm_weight']}",
                f"- Recommended mape_nonzero: {rec['mape_nonzero']:.6f}",
            ]
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic daily replay simulation")
    parser.add_argument("--dataset-dir", default="data/kaggle/favorita")
    parser.add_argument("--holdout-days", type=int, default=365)
    parser.add_argument("--customer-id", default="00000000-0000-0000-0000-000000000001")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--retrain-cadence", choices=["weekly", "daily", "none"], default="weekly")
    parser.add_argument("--forecast-horizon", type=int, default=14)
    parser.add_argument("--portfolio-mode", choices=["off", "auto"], default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default="docs/productization_artifacts")
    parser.add_argument("--max-training-rows", type=int, default=400000)
    parser.add_argument("--max-replay-days", type=int, default=365)
    parser.add_argument("--portfolio-eval-rows", type=int, default=10000)
    parser.add_argument("--drift-mape-threshold", type=float, default=0.28)
    parser.add_argument("--po-decisions-per-day", type=int, default=3)
    parser.add_argument("--db-max-rows-per-day", type=int, default=2000)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = load_canonical_transactions(args.dataset_dir)
    raw = raw.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    dataset_id = str(raw["dataset_id"].iloc[0]) if len(raw) and "dataset_id" in raw.columns else "unknown"
    source_paths = [str(p.resolve()) for p in sorted(Path(args.dataset_dir).rglob("*.csv")) if p.is_file()]

    partition = build_time_partition(
        raw,
        holdout_days=args.holdout_days,
        train_end_date=None,
        dataset_id=dataset_id,
        source_paths=source_paths,
    )
    partition_manifest_path = output_dir / "replay_partition_manifest.json"
    write_partition_manifest(partition["metadata"], str(partition_manifest_path))

    train_end = pd.to_datetime(partition["metadata"]["train_end_date"]).date()

    features = create_features(raw, force_tier="cold_start")
    features = features.sort_values(["date", "store_id", "product_id"]).reset_index(drop=True)
    features["date"] = pd.to_datetime(features["date"]).dt.date

    holdout_df = features[features["date"] > train_end].copy()
    if holdout_df.empty:
        raise ValueError("Holdout partition is empty; cannot run replay")

    if args.start_date:
        start_date = pd.to_datetime(args.start_date).date()
        holdout_df = holdout_df[holdout_df["date"] >= start_date]
    if args.end_date:
        end_date = pd.to_datetime(args.end_date).date()
        holdout_df = holdout_df[holdout_df["date"] <= end_date]

    replay_dates = sorted(holdout_df["date"].unique().tolist())
    if args.max_replay_days > 0:
        replay_dates = replay_dates[: args.max_replay_days]
    if not replay_dates:
        raise ValueError("No replay dates available after start/end filters")

    feature_cols = [c for c in get_feature_cols("cold_start") if c in features.columns]

    daily_log_path = output_dir / "replay_daily_log.jsonl"
    decisions_path = output_dir / "replay_hitl_decisions.json"
    summary_json_path = output_dir / "replay_summary.json"
    summary_md_path = output_dir / "replay_summary.md"
    strategy_md_path = output_dir / "replay_model_strategy_decision.md"

    daily_log_path.write_text("", encoding="utf-8")

    current_model = None
    current_version = None
    model_seq = 0
    champion_version = None
    version_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)
    version_decided: set[str] = set()
    trigger_events: list[dict[str, Any]] = []
    hitl_decisions: list[dict[str, Any]] = []

    retrain_count = 0
    critical_failures = 0
    db_forecast_rows_written = 0
    db_accuracy_rows_written = 0

    db_adapter = ReplayDbAdapter(
        customer_id=args.customer_id,
        enabled=not bool(args.dry_run),
        max_rows_per_day=args.db_max_rows_per_day,
    )
    if db_adapter.enabled:
        asyncio.run(db_adapter.open())

    def train_model(history_date: date) -> tuple[Any, str]:
        nonlocal model_seq, retrain_count
        train_slice = features[features["date"] <= history_date].copy()
        if train_slice.empty:
            raise ValueError("No train rows available for requested history_date")
        train_slice = _limit_training_rows(train_slice, args.max_training_rows)
        model, _ = train_xgboost(
            train_slice,
            feature_cols=feature_cols,
            params={
                "n_estimators": 300,
                "max_depth": 6,
                "learning_rate": 0.05,
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "early_stopping_rounds": 20,
                "random_state": 42,
            },
        )
        model_seq += 1
        retrain_count += 1
        return model, f"replay_v{model_seq}"

    try:
        for idx, day in enumerate(replay_dates):
            day_record: dict[str, Any] = {
                "date": day.isoformat(),
                "forecast_horizon": int(args.forecast_horizon),
                "customer_id": args.customer_id,
                "dry_run": bool(args.dry_run),
            }
            try:
                retrain_reasons: list[str] = []

                if current_model is None:
                    retrain_reasons.append("initial")
                elif args.retrain_cadence == "daily":
                    retrain_reasons.append("scheduled_daily")
                elif args.retrain_cadence == "weekly" and idx > 0 and idx % 7 == 0:
                    retrain_reasons.append("scheduled_weekly")

                # Drift trigger from rolling recent days on active version.
                if current_version and version_metrics[current_version]:
                    recent = version_metrics[current_version][-14:]
                    recent_mape = _weighted_metric(recent, "mape_nonzero")
                    if recent_mape > args.drift_mape_threshold:
                        retrain_reasons.append("drift_detected")

                if retrain_reasons:
                    history_date = day - timedelta(days=1)
                    current_model, current_version = train_model(history_date)
                    trigger_events.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "date": day.isoformat(),
                            "event": "retrain",
                            "reasons": sorted(set(retrain_reasons)),
                            "version": current_version,
                            "train_end_date": history_date.isoformat(),
                        }
                    )
                    if db_adapter.enabled:
                        asyncio.run(
                            db_adapter.record_retrain_event(
                                replay_date=day,
                                model_version=current_version,
                                retrain_reasons=retrain_reasons,
                                train_end_date=history_date,
                            )
                        )

                day_rows = features[features["date"] == day].copy()
                if day_rows.empty:
                    day_record["status"] = "skipped_no_rows"
                    with daily_log_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(day_record) + "\n")
                    continue

                X_day = day_rows[feature_cols].fillna(0)
                y_day = day_rows["quantity"].astype(float)
                preds = np.maximum(current_model.predict(X_day), 0.0)
                bundle = compute_forecast_metrics(y_day, preds)

                metric_row = {
                    "date": day.isoformat(),
                    "samples": int(len(day_rows)),
                    "mae": float(bundle["mae"]),
                    "mape_nonzero": float(bundle["mape_nonzero"]),
                    "stockout_miss_rate": float(bundle["stockout_miss_rate"]),
                    "overstock_rate": float(bundle["overstock_rate"]),
                }
                version_metrics[current_version].append(metric_row)

                if db_adapter.enabled:
                    day_forecast_rows, day_accuracy_rows = asyncio.run(
                        db_adapter.persist_day_metrics(
                            replay_date=day,
                            day_rows=day_rows,
                            preds=preds,
                            model_version=current_version,
                        )
                    )
                    db_forecast_rows_written += day_forecast_rows
                    db_accuracy_rows_written += day_accuracy_rows
                else:
                    day_forecast_rows, day_accuracy_rows = 0, 0

                # HITL PO decisions
                po_counts = {"approve": 0, "edit": 0, "reject": 0}
                if args.po_decisions_per_day > 0:
                    scored = day_rows[["store_id", "product_id"]].copy()
                    scored["actual_qty"] = y_day.values
                    scored["forecast_qty"] = preds
                    scored["abs_err"] = np.abs(scored["actual_qty"] - scored["forecast_qty"])
                    reviewed = scored.sort_values("abs_err", ascending=False).head(args.po_decisions_per_day)
                    for row in reviewed.itertuples(index=False):
                        suggested_qty = int(max(round(float(row.forecast_qty)), 1))
                        key = f"{day.isoformat()}::{row.store_id}::{row.product_id}"
                        action = decide_po_action(
                            forecast_qty=float(row.forecast_qty),
                            actual_qty=float(row.actual_qty),
                            suggested_qty=suggested_qty,
                            decision_key=key,
                        )
                        po_counts[action.action] += 1
                        hitl_decisions.append(
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "decision_type": f"po_{action.action}",
                                "reason_code": action.reason_code,
                                "impacted_entity_id": f"{row.store_id}:{row.product_id}:{day.isoformat()}",
                                "payload": {
                                    "forecast_qty": float(row.forecast_qty),
                                    "actual_qty": float(row.actual_qty),
                                    "final_quantity": int(action.final_quantity),
                                },
                            }
                        )

                # Model promotion HITL decision (once per version after 30 replay days observed).
                promotion_event = None
                version_days_seen = len(version_metrics[current_version])
                if current_version and current_version not in version_decided and version_days_seen >= 30:
                    candidate_summary = {
                        "mae": _weighted_metric(version_metrics[current_version], "mae"),
                        "mape_nonzero": _weighted_metric(version_metrics[current_version], "mape_nonzero"),
                        "stockout_miss_rate": _weighted_metric(version_metrics[current_version], "stockout_miss_rate"),
                        "overstock_rate": _weighted_metric(version_metrics[current_version], "overstock_rate"),
                    }
                    champion_summary = None
                    if champion_version:
                        champion_summary = {
                            "mae": _weighted_metric(version_metrics[champion_version], "mae"),
                            "mape_nonzero": _weighted_metric(version_metrics[champion_version], "mape_nonzero"),
                            "stockout_miss_rate": _weighted_metric(
                                version_metrics[champion_version], "stockout_miss_rate"
                            ),
                            "overstock_rate": _weighted_metric(version_metrics[champion_version], "overstock_rate"),
                        }

                    gate_passed = _promotion_gate_pass(
                        candidate_metrics=candidate_summary, champion_metrics=champion_summary
                    )
                    decision = decide_model_promotion(
                        gate_passed=gate_passed,
                        candidate_mape_nonzero=candidate_summary["mape_nonzero"],
                        candidate_stockout_miss_rate=candidate_summary["stockout_miss_rate"],
                        decision_key=f"model::{current_version}",
                    )
                    version_decided.add(current_version)
                    if decision.action == "approve":
                        champion_version = current_version

                    promotion_event = {
                        "model_version": current_version,
                        "gate_passed": gate_passed,
                        "decision": decision.action,
                        "reason_code": decision.reason_code,
                        "candidate_summary": candidate_summary,
                        "champion_version": champion_version,
                    }
                    hitl_decisions.append(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "decision_type": f"model_promote_{decision.action}",
                            "reason_code": decision.reason_code,
                            "impacted_entity_id": current_version,
                            "payload": promotion_event,
                        }
                    )
                    if db_adapter.enabled:
                        asyncio.run(
                            db_adapter.record_promotion_decision(
                                model_version=current_version,
                                decision=decision.action,
                                reason_code=decision.reason_code,
                                gate_passed=gate_passed,
                                candidate_summary=candidate_summary,
                            )
                        )

                day_record.update(
                    {
                        "status": "success",
                        "model_version": current_version,
                        "metrics": metric_row,
                        "retrain_triggered": bool(retrain_reasons),
                        "retrain_reasons": sorted(set(retrain_reasons)),
                        "po_decision_counts": po_counts,
                        "promotion_event": promotion_event,
                        "db_rows_written": {
                            "demand_forecasts": day_forecast_rows,
                            "forecast_accuracy": day_accuracy_rows,
                        },
                    }
                )
            except Exception as exc:  # noqa: BLE001
                critical_failures += 1
                day_record.update(
                    {
                        "status": "failed",
                        "error": str(exc),
                        "model_version": current_version,
                    }
                )

            with daily_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(day_record) + "\n")
    finally:
        if db_adapter.enabled:
            asyncio.run(db_adapter.close())

    all_daily_metrics: list[dict[str, Any]] = []
    for rows in version_metrics.values():
        all_daily_metrics.extend(rows)

    baseline_metrics = {
        "mae": _weighted_metric(all_daily_metrics, "mae"),
        "mape_nonzero": _weighted_metric(all_daily_metrics, "mape_nonzero"),
        "stockout_miss_rate": _weighted_metric(all_daily_metrics, "stockout_miss_rate"),
        "overstock_rate": _weighted_metric(all_daily_metrics, "overstock_rate"),
        "critical_failures": float(critical_failures),
    }

    thresholds = ReplayThresholds()
    baseline_gate_passed, baseline_gate_failures = _evaluate_baseline_gate(baseline_metrics, thresholds)

    hitl_counts = defaultdict(int)
    for decision in hitl_decisions:
        hitl_counts[decision["decision_type"]] += 1

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": dataset_id,
        "customer_id": args.customer_id,
        "dry_run": bool(args.dry_run),
        "replay_start": replay_dates[0].isoformat(),
        "replay_end": replay_dates[-1].isoformat(),
        "replay_days": int(len(replay_dates)),
        "partition_manifest": str(partition_manifest_path),
        "retrain_count": int(retrain_count),
        "critical_failures": int(critical_failures),
        "trigger_events": trigger_events,
        "baseline_metrics": baseline_metrics,
        "baseline_gate_passed": baseline_gate_passed,
        "baseline_gate_failures": baseline_gate_failures,
        "champion_version": champion_version,
        "hitl_counts": dict(sorted(hitl_counts.items())),
        "db_persistence": {
            "enabled": bool(db_adapter.enabled),
            "demand_forecast_rows_written": int(db_forecast_rows_written),
            "forecast_accuracy_rows_written": int(db_accuracy_rows_written),
            "max_rows_per_day": int(args.db_max_rows_per_day),
        },
        "artifacts": {
            "daily_log": str(daily_log_path),
            "summary_json": str(summary_json_path),
            "summary_md": str(summary_md_path),
            "hitl_decisions_json": str(decisions_path),
            "strategy_md": str(strategy_md_path),
        },
    }

    if args.portfolio_mode == "auto" and not baseline_gate_passed:
        portfolio = _evaluate_portfolio(
            features_df=features,
            train_end_date=train_end,
            feature_cols=feature_cols,
            max_training_rows=args.max_training_rows,
            max_eval_rows=args.portfolio_eval_rows,
        )
        summary["portfolio"] = portfolio

    decisions_path.write_text(json.dumps(hitl_decisions, indent=2), encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _render_summary_md(summary, summary_md_path)
    _render_strategy_md(summary, strategy_md_path)

    print(json.dumps(
        {
            "status": "success",
            "summary_json": str(summary_json_path),
            "summary_md": str(summary_md_path),
            "daily_log": str(daily_log_path),
            "hitl_decisions": str(decisions_path),
            "strategy_md": str(strategy_md_path),
            "baseline_gate_passed": baseline_gate_passed,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
