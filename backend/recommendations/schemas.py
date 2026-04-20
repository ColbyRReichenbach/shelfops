from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: uuid.UUID
    customer_id: uuid.UUID
    store_id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    linked_po_id: uuid.UUID | None = None
    status: str
    forecast_model_version: str
    policy_version: str
    horizon_days: int
    forecast_start_date: date
    forecast_end_date: date
    recommended_quantity: int
    quantity_available: int
    quantity_on_order: int
    inventory_position: int
    reorder_point: int
    safety_stock: int
    economic_order_qty: int
    lead_time_days: int
    service_level: float
    estimated_unit_cost: float | None = None
    estimated_total_cost: float | None = None
    source_type: str | None = None
    source_id: uuid.UUID | None = None
    source_name: str | None = None
    horizon_demand_mean: float
    horizon_demand_lower: float | None = None
    horizon_demand_upper: float | None = None
    lead_time_demand_mean: float
    lead_time_demand_upper: float | None = None
    interval_method: str | None = None
    calibration_status: str | None = None
    interval_coverage: float | None = None
    no_order_stockout_risk: str
    order_overstock_risk: str
    recommendation_rationale: dict[str, Any]
    created_at: datetime
