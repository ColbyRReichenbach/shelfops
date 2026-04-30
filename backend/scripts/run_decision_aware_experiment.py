#!/usr/bin/env python3
"""Run a decision-aware M5 benchmark experiment and optionally persist it."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import get_settings
from db.models import DatasetSnapshot, ModelExperiment, ModelVersion
from ml.decision_experiment import (
    DEFAULT_DATA_DIR,
    DEFAULT_EXPERIMENT_NAME,
    DEFAULT_HYPOTHESIS,
    DecisionExperimentConfig,
    run_decision_aware_experiment,
)
from scripts.production_tenant import PRODUCTION_CUSTOMER_ID, ensure_production_tenant

DEFAULT_OUTPUT_JSON = "backend/reports/experiments/m5_decision_aware_experiment.json"
DEFAULT_OUTPUT_MD = "backend/reports/experiments/m5_decision_aware_experiment.md"


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


async def _upsert_snapshot(db, snapshot: dict[str, Any]) -> None:
    existing = await db.get(DatasetSnapshot, snapshot["snapshot_id"])
    payload = {
        "dataset_id": snapshot["dataset_id"],
        "source_type": snapshot["source_type"],
        "row_count": int(snapshot["row_count"]),
        "store_count": int(snapshot["store_count"]),
        "product_count": int(snapshot["product_count"]),
        "date_min": _parse_date(snapshot.get("date_min")),
        "date_max": _parse_date(snapshot.get("date_max")),
        "content_hash": snapshot["content_hash"],
        "schema_version": snapshot["schema_version"],
        "frequency": snapshot["frequency"],
        "forecast_grain": snapshot["forecast_grain"],
        "geography": snapshot["geography"],
        "implementation_status": snapshot["implementation_status"],
        "claim_boundaries_ref": snapshot.get("claim_boundaries_ref") or "data_registry/datasets.yaml",
    }
    if existing is None:
        db.add(DatasetSnapshot(snapshot_id=snapshot["snapshot_id"], customer_id=None, **payload))
    else:
        for key, value in payload.items():
            setattr(existing, key, value)


async def _upsert_model_version(
    db,
    *,
    report: dict[str, Any],
    output_json: str,
) -> None:
    challenger = report["challenger"]
    experiment = report["experiment"]
    lineage = dict(challenger.get("lineage_metadata") or {})
    metrics = {
        **dict(challenger.get("holdout_metrics") or {}),
        **lineage,
        "decision_replay": report["decision_replay"]["results"]["challenger"],
        "promotion_comparison": report["promotion_comparison"],
        "report_artifact": output_json,
        "provenance": "benchmark",
        "claim_boundary": report["claim_boundary"],
    }
    existing = (
        await db.execute(
            select(ModelVersion).where(
                ModelVersion.customer_id == PRODUCTION_CUSTOMER_ID,
                ModelVersion.model_name == experiment["model_name"],
                ModelVersion.version == challenger["version"],
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ModelVersion(
            customer_id=PRODUCTION_CUSTOMER_ID,
            model_name=experiment["model_name"],
            version=challenger["version"],
        )
        db.add(existing)
    existing.status = "challenger"
    existing.routing_weight = 0.0
    existing.metrics = metrics
    existing.smoke_test_passed = True
    existing.promoted_at = None
    existing.archived_at = None


async def _upsert_experiment_ledger(
    db,
    *,
    report: dict[str, Any],
    output_json: str,
    output_md: str,
) -> str:
    experiment = report["experiment"]
    results = {
        "lineage_metadata": report["lineage_metadata"],
        "run_report": report,
        "arena_breakdown": report["promotion_comparison"],
        "promotion_comparison": report["promotion_comparison"],
        "baseline_wape": report["baseline"]["holdout_metrics"].get("wape"),
        "experimental_wape": report["challenger"]["holdout_metrics"].get("wape"),
        "baseline_mase": report["baseline"]["holdout_metrics"].get("mase"),
        "experimental_mase": report["challenger"]["holdout_metrics"].get("mase"),
        "overall_business_safe": report.get("overall_business_safe"),
        "execution": {
            "ran_by": "decision_experiment_script",
            "ran_at": report["generated_at"],
            "artifact_json": output_json,
            "artifact_md": output_md,
        },
    }
    existing = (
        await db.execute(
            select(ModelExperiment).where(
                ModelExperiment.customer_id == PRODUCTION_CUSTOMER_ID,
                ModelExperiment.experiment_name == experiment["experiment_name"],
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ModelExperiment(
            customer_id=PRODUCTION_CUSTOMER_ID,
            experiment_name=experiment["experiment_name"],
            hypothesis=experiment["hypothesis"],
            experiment_type=experiment["experiment_type"],
            model_name=experiment["model_name"],
            proposed_by="decision_experiment_script",
        )
        db.add(existing)

    existing.hypothesis = experiment["hypothesis"]
    existing.experiment_type = experiment["experiment_type"]
    existing.model_name = experiment["model_name"]
    existing.baseline_version = experiment["baseline_version"]
    existing.experimental_version = experiment["experimental_version"]
    existing.status = "shadow_testing"
    existing.approved_by = existing.approved_by or "decision_experiment_script"
    existing.approved_at = existing.approved_at or datetime.utcnow()
    existing.results = results
    existing.decision_rationale = experiment["decision_rationale"]
    existing.completed_at = None
    await db.flush()
    return str(existing.experiment_id)


async def persist_report(report: dict[str, Any], *, output_json: str, output_md: str) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=settings.database_echo, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        await ensure_production_tenant(db, wipe_synthetic=False)
        await _upsert_snapshot(db, report["dataset"])
        await _upsert_model_version(db, report=report, output_json=output_json)
        experiment_id = await _upsert_experiment_ledger(db, report=report, output_json=output_json, output_md=output_md)
        await db.commit()
    await engine.dispose()
    return {
        "customer_id": str(PRODUCTION_CUSTOMER_ID),
        "experiment_id": experiment_id,
        "model_version": report["challenger"]["version"],
        "status": "shadow_testing",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the M5 decision-aware benchmark experiment")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--dataset-id", default="m5_walmart")
    parser.add_argument("--baseline-version", default="v3")
    parser.add_argument("--challenger-version", default="e_m5_decision_v1")
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME)
    parser.add_argument("--hypothesis", default=DEFAULT_HYPOTHESIS)
    parser.add_argument("--holdout-days", type=int, default=28)
    parser.add_argument("--calibration-days", type=int, default=28)
    parser.add_argument("--max-rows", type=int, default=120_000)
    parser.add_argument("--max-series", type=int, default=60)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--persist", action="store_true", help="Persist challenger and experiment ledger rows")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = DecisionExperimentConfig(
        dataset_id=args.dataset_id,
        baseline_version=args.baseline_version,
        challenger_version=args.challenger_version,
        experiment_name=args.experiment_name,
        hypothesis=args.hypothesis,
        holdout_days=args.holdout_days,
        calibration_days=args.calibration_days,
        max_rows=args.max_rows,
        max_series=args.max_series,
    )
    report = run_decision_aware_experiment(
        data_dir=args.data_dir,
        config=config,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    persistence = None
    if args.persist:
        persistence = asyncio.run(persist_report(report, output_json=args.output_json, output_md=args.output_md))

    summary = {
        "report_json": args.output_json,
        "report_md": args.output_md,
        "baseline_wape": report["baseline"]["holdout_metrics"].get("wape"),
        "challenger_wape": report["challenger"]["holdout_metrics"].get("wape"),
        "benchmark_gates_passed": report["promotion_comparison"].get("benchmark_gates_passed"),
        "decision": report["promotion_comparison"].get("decision"),
        "persistence": persistence,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
