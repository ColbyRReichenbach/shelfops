"""
Deterministic HITL policies for replay simulations.

These policies intentionally avoid randomness so replay outputs are reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

POActionType = Literal["approve", "edit", "reject"]
ModelPromotionActionType = Literal["approve", "reject"]


@dataclass(frozen=True)
class POAction:
    action: POActionType
    reason_code: str
    final_quantity: int


@dataclass(frozen=True)
class ModelPromotionDecision:
    action: ModelPromotionActionType
    reason_code: str


def _stable_unit_interval(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    value = int(digest[:12], 16)
    return (value % 1_000_000) / 1_000_000.0


def decide_po_action(
    *,
    forecast_qty: float,
    actual_qty: float,
    suggested_qty: int,
    decision_key: str,
) -> POAction:
    """
    Decide approve/edit/reject for a suggested PO using deterministic rules.
    """
    forecast_qty = float(max(forecast_qty, 0.0))
    actual_qty = float(max(actual_qty, 0.0))
    suggested_qty = int(max(suggested_qty, 0))

    error = forecast_qty - actual_qty
    abs_error = abs(error)
    tolerance = max(3.0, actual_qty * 0.20)
    jitter = _stable_unit_interval(decision_key)

    # Significant over-forecast: prefer reject with occasional quantity edit.
    if error > tolerance:
        if jitter < 0.15:
            edited_qty = int(max(round(actual_qty * 1.05), 1))
            return POAction(action="edit", reason_code="forecast_adjustment", final_quantity=edited_qty)
        return POAction(action="reject", reason_code="overstock", final_quantity=0)

    # Significant under-forecast: edit upward.
    if error < -tolerance:
        uplift = 1.10 + (0.10 * jitter)
        edited_qty = int(max(round(actual_qty * uplift), suggested_qty + 1, 1))
        return POAction(action="edit", reason_code="forecast_disagree", final_quantity=edited_qty)

    # Near target: mostly approve, rare conservative edit.
    if abs_error <= max(1.0, tolerance * 0.5) and jitter >= 0.08:
        return POAction(action="approve", reason_code="within_tolerance", final_quantity=suggested_qty)

    adjusted_qty = int(max(round((forecast_qty + actual_qty) / 2.0), 1))
    return POAction(action="edit", reason_code="manual_review", final_quantity=adjusted_qty)


def decide_model_promotion(
    *,
    gate_passed: bool,
    candidate_mape_nonzero: float | None,
    candidate_stockout_miss_rate: float | None,
    decision_key: str,
) -> ModelPromotionDecision:
    """
    Deterministic reviewer policy for candidate model promotion.
    """
    if not gate_passed:
        return ModelPromotionDecision(action="reject", reason_code="gate_failed")

    if candidate_mape_nonzero is None or candidate_stockout_miss_rate is None:
        return ModelPromotionDecision(action="reject", reason_code="insufficient_metrics")

    # Guardrail policy: approvals require baseline KPI quality.
    if candidate_mape_nonzero > 0.22:
        return ModelPromotionDecision(action="reject", reason_code="mape_above_threshold")
    if candidate_stockout_miss_rate > 0.08:
        return ModelPromotionDecision(action="reject", reason_code="stockout_risk_high")

    # Keep a small deterministic reject slice for conservative governance signal.
    jitter = _stable_unit_interval(decision_key)
    if jitter < 0.05:
        return ModelPromotionDecision(action="reject", reason_code="manual_conservative_hold")

    return ModelPromotionDecision(action="approve", reason_code="approved_after_gate")
