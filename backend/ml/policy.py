from __future__ import annotations

import math

POLICY_VERSION = "replenishment_v1"


def compute_inventory_position(quantity_available: int, quantity_on_order: int) -> int:
    return max(0, int(quantity_available)) + max(0, int(quantity_on_order))


def compute_recommended_quantity(
    *,
    inventory_position: int,
    reorder_point: int,
    economic_order_qty: int,
    min_order_qty: int,
) -> int:
    target_position = max(0, int(reorder_point)) + max(0, int(economic_order_qty))
    raw_quantity = max(0, target_position - max(0, int(inventory_position)))
    if raw_quantity <= 0:
        return 0
    constrained = max(int(min_order_qty or 1), raw_quantity)
    return int(constrained)


def classify_no_order_stockout_risk(
    *,
    inventory_position: int,
    lead_time_demand_mean: float,
    lead_time_demand_upper: float,
) -> str:
    inventory = float(max(0, inventory_position))
    if inventory <= max(0.0, float(lead_time_demand_mean)):
        return "high"
    if inventory <= max(0.0, float(lead_time_demand_upper)):
        return "medium"
    return "low"


def classify_order_overstock_risk(
    *,
    inventory_position: int,
    recommended_quantity: int,
    horizon_demand_mean: float,
    horizon_demand_lower: float,
    safety_stock: int,
    economic_order_qty: int,
) -> str:
    if recommended_quantity <= 0:
        return "low"

    post_order_inventory = max(0, int(inventory_position)) + max(0, int(recommended_quantity))
    expected_leftover = post_order_inventory - max(0.0, float(horizon_demand_mean))
    conservative_leftover = post_order_inventory - max(0.0, float(horizon_demand_lower))

    if conservative_leftover > max(1, int(economic_order_qty)):
        return "high"
    if expected_leftover > max(0, int(safety_stock)):
        return "medium"
    return "low"


def estimate_total_cost(*, recommended_quantity: int, unit_cost: float | None) -> float | None:
    if unit_cost is None:
        return None
    return round(max(0, int(recommended_quantity)) * float(unit_cost), 2)


def round_lead_time_days(value: float) -> int:
    return max(1, int(math.ceil(float(value))))
