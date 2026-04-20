from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import pstdev
from typing import Sequence

import pandas as pd

from db.models import DemandForecast
from ml.business_metrics import calculate_business_impact_metrics


@dataclass(frozen=True)
class ForecastWindowSummary:
    start_date: date
    end_date: date
    horizon_days: int
    avg_daily_demand: float
    demand_std_dev: float
    horizon_demand_mean: float
    horizon_demand_lower: float | None
    horizon_demand_upper: float | None
    lead_time_demand_mean: float
    lead_time_demand_upper: float | None


@dataclass(frozen=True)
class RecommendationOutcomeSummary:
    actual_sales_qty: float
    actual_demand_qty: float
    ending_inventory_qty: int | None
    stockout_event: bool
    overstock_event: bool
    forecast_error_abs: float
    estimated_stockout_value: float | None
    estimated_overstock_cost: float | None
    net_estimated_value: float | None
    demand_confidence: str
    value_confidence: str
    status: str


@dataclass(frozen=True)
class RecommendationPolicyImpactSummary:
    decision_quantity: int
    baseline_quantity: int
    avoided_stockout_value: float | None
    incremental_overstock_cost: float | None
    net_policy_value: float | None
    value_confidence: str


def summarize_forecast_window(
    forecasts: Sequence[DemandForecast],
    *,
    lead_time_days: int,
) -> ForecastWindowSummary:
    if not forecasts:
        raise ValueError("at least one forecast row is required")

    ordered = sorted(forecasts, key=lambda row: row.forecast_date)
    means = [float(row.forecasted_demand or 0.0) for row in ordered]
    lowers = [float(row.lower_bound) for row in ordered if row.lower_bound is not None]
    uppers = [float(row.upper_bound) for row in ordered if row.upper_bound is not None]
    lead_slice = ordered[: max(1, int(lead_time_days))]

    return ForecastWindowSummary(
        start_date=ordered[0].forecast_date,
        end_date=ordered[-1].forecast_date,
        horizon_days=len(ordered),
        avg_daily_demand=round(sum(means) / len(means), 4),
        demand_std_dev=round(pstdev(means) if len(means) > 1 else 0.0, 4),
        horizon_demand_mean=round(sum(means), 4),
        horizon_demand_lower=round(sum(lowers), 4) if len(lowers) == len(ordered) else None,
        horizon_demand_upper=round(sum(uppers), 4) if len(uppers) == len(ordered) else None,
        lead_time_demand_mean=round(sum(float(row.forecasted_demand or 0.0) for row in lead_slice), 4),
        lead_time_demand_upper=(
            round(sum(float(row.upper_bound or 0.0) for row in lead_slice), 4)
            if all(row.upper_bound is not None for row in lead_slice)
            else None
        ),
    )


def compute_recommendation_outcome(
    *,
    horizon_demand_mean: float,
    actual_sales_qty: float,
    ending_inventory_qty: int | None,
    horizon_end_date: date,
    as_of_date: date,
    recommended_quantity: int,
    safety_stock: int,
    unit_cost: float | None,
    unit_price: float | None,
    holding_cost_per_unit_per_day: float | None,
) -> RecommendationOutcomeSummary:
    actual_sales_qty = float(actual_sales_qty or 0.0)
    # Latent-demand recovery is not yet wired into the closeout loop, so this field
    # remains an observed-sales proxy rather than measured unconstrained demand.
    actual_demand_qty = actual_sales_qty
    closed = as_of_date > horizon_end_date
    demand_confidence = "estimated" if closed else "provisional"

    stockout_event = ending_inventory_qty is not None and ending_inventory_qty <= 0
    overstock_event = ending_inventory_qty is not None and ending_inventory_qty > max(0, int(safety_stock))
    forecast_error_abs = round(abs(float(horizon_demand_mean) - actual_demand_qty), 4)

    metrics = calculate_business_impact_metrics(
        pd.DataFrame(
            [
                {
                    "predicted_qty": float(horizon_demand_mean),
                    "actual_qty": actual_demand_qty,
                    "unit_price": unit_price,
                    "unit_cost": unit_cost,
                    "holding_cost_per_unit_per_day": holding_cost_per_unit_per_day,
                }
            ]
        )
    )
    stockout_value = float(metrics["opportunity_cost_stockout"] or 0.0)
    overstock_cost = float(metrics["opportunity_cost_overstock"] or 0.0)
    value_confidence = (
        "provisional"
        if not closed
        else _combine_confidence_labels(
            str(metrics.get("opportunity_cost_stockout_confidence", "unavailable")),
            str(metrics.get("opportunity_cost_overstock_confidence", "unavailable")),
        )
    )
    net_estimated_value = round(stockout_value - overstock_cost, 4)

    return RecommendationOutcomeSummary(
        actual_sales_qty=round(actual_sales_qty, 4),
        actual_demand_qty=round(actual_demand_qty, 4),
        ending_inventory_qty=ending_inventory_qty,
        stockout_event=stockout_event,
        overstock_event=overstock_event,
        forecast_error_abs=forecast_error_abs,
        estimated_stockout_value=round(stockout_value, 4),
        estimated_overstock_cost=round(overstock_cost, 4),
        net_estimated_value=net_estimated_value,
        demand_confidence=demand_confidence,
        value_confidence=value_confidence,
        status="closed" if closed else "provisional",
    )


def compute_decision_policy_impact(
    *,
    inventory_position: int,
    decision_quantity: int,
    actual_sales_qty: float,
    unit_cost: float | None,
    unit_price: float | None,
    holding_cost_per_unit_per_day: float | None,
) -> RecommendationPolicyImpactSummary:
    baseline_quantity = max(0, int(inventory_position or 0))
    decision_quantity = max(0, int(decision_quantity or 0))
    policy_quantity = baseline_quantity + decision_quantity

    baseline_metrics = calculate_business_impact_metrics(
        pd.DataFrame(
            [
                {
                    "predicted_qty": float(baseline_quantity),
                    "actual_qty": float(actual_sales_qty or 0.0),
                    "unit_price": unit_price,
                    "unit_cost": unit_cost,
                    "holding_cost_per_unit_per_day": holding_cost_per_unit_per_day,
                }
            ]
        )
    )
    policy_metrics = calculate_business_impact_metrics(
        pd.DataFrame(
            [
                {
                    "predicted_qty": float(policy_quantity),
                    "actual_qty": float(actual_sales_qty or 0.0),
                    "unit_price": unit_price,
                    "unit_cost": unit_cost,
                    "holding_cost_per_unit_per_day": holding_cost_per_unit_per_day,
                }
            ]
        )
    )

    baseline_stockout = _optional_float(baseline_metrics.get("opportunity_cost_stockout"))
    policy_stockout = _optional_float(policy_metrics.get("opportunity_cost_stockout"))
    baseline_overstock = _optional_float(baseline_metrics.get("opportunity_cost_overstock"))
    policy_overstock = _optional_float(policy_metrics.get("opportunity_cost_overstock"))

    avoided_stockout_value = (
        round(max(0.0, baseline_stockout - policy_stockout), 4)
        if baseline_stockout is not None and policy_stockout is not None
        else None
    )
    incremental_overstock_cost = (
        round(max(0.0, policy_overstock - baseline_overstock), 4)
        if baseline_overstock is not None and policy_overstock is not None
        else None
    )
    net_policy_value = (
        round((avoided_stockout_value or 0.0) - (incremental_overstock_cost or 0.0), 4)
        if avoided_stockout_value is not None and incremental_overstock_cost is not None
        else None
    )

    value_confidence = _combine_confidence_labels(
        str(baseline_metrics.get("opportunity_cost_stockout_confidence", "unavailable")),
        str(policy_metrics.get("opportunity_cost_stockout_confidence", "unavailable")),
        str(baseline_metrics.get("opportunity_cost_overstock_confidence", "unavailable")),
        str(policy_metrics.get("opportunity_cost_overstock_confidence", "unavailable")),
    )
    if net_policy_value is None:
        value_confidence = "unavailable"

    return RecommendationPolicyImpactSummary(
        decision_quantity=decision_quantity,
        baseline_quantity=baseline_quantity,
        avoided_stockout_value=avoided_stockout_value,
        incremental_overstock_cost=incremental_overstock_cost,
        net_policy_value=net_policy_value,
        value_confidence=value_confidence,
    )


def _combine_confidence_labels(*labels: str) -> str:
    normalized = [label for label in labels if label and label != "unavailable"]
    if not normalized:
        return "unavailable"
    if all(label == "measured" for label in normalized):
        return "measured"
    if any(label == "estimated" for label in normalized):
        return "estimated"
    return normalized[0]


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return float(value)
