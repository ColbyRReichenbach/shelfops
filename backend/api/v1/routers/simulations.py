from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ml.replenishment_simulation import (
    DEFAULT_DATA_DIR,
    DEFAULT_OUTPUT_JSON,
    SimulationConfig,
    load_simulation_report,
    run_replenishment_simulation,
)

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])


class SimulationPolicyRow(BaseModel):
    policy_name: str
    stockout_days: int
    lost_sales_units: float
    lost_sales_proxy: float
    overstock_units: float
    overstock_dollars: float
    service_level: float
    po_count: int
    combined_cost_proxy: float


class ReplenishmentSimulationResponse(BaseModel):
    dataset_id: str
    dataset_snapshot_id: str | None = None
    simulation_scope: str
    impact_confidence: str
    claim_boundary: str
    stockout_label_boundary: str
    inventory_assumptions_confidence: str
    po_assumptions_confidence: str
    lead_time_assumptions_confidence: str
    cost_assumptions_confidence: str
    model_version: str | None = None
    policy_version: str | None = None
    policy_versions: list[str]
    rows_used: int
    series_used: int
    history_start: str
    history_end: str
    replay_start: str
    replay_end: str
    results: list[SimulationPolicyRow]


@router.get("/replenishment", response_model=ReplenishmentSimulationResponse)
async def get_replenishment_simulation(
    refresh: bool = Query(False),
    dataset_id: str = Query("m5_walmart"),
    data_dir: str = Query(DEFAULT_DATA_DIR),
    replay_days: int = Query(28, ge=7, le=365),
    warmup_days: int = Query(56, ge=14, le=730),
    max_series: int = Query(50, ge=1, le=1000),
    report_path: str = Query(DEFAULT_OUTPUT_JSON),
):
    path = Path(report_path)
    if refresh or not path.exists():
        try:
            report = run_replenishment_simulation(
                data_dir=data_dir,
                config=SimulationConfig(
                    dataset_id=dataset_id,
                    replay_days=replay_days,
                    warmup_days=warmup_days,
                    max_series=max_series,
                ),
                output_json=path,
                output_md=path.with_suffix(".md"),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        report = load_simulation_report(path)
    return report
