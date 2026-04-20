from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    DemandForecast,
    InventoryLevel,
    PODecision,
    Product,
    PurchaseOrder,
    ReorderPoint,
    ReplenishmentRecommendation,
    Store,
    Supplier,
)
from inventory.optimizer import (
    InventoryOptimizer,
    get_cluster_multipliers,
    get_default_service_level,
    get_reliability_multiplier,
    get_z_score,
)
from ml.policy import (
    POLICY_VERSION,
    classify_no_order_stockout_risk,
    classify_order_overstock_risk,
    compute_inventory_position,
    compute_recommended_quantity,
    estimate_total_cost,
    round_lead_time_days,
)
from recommendations.outcomes import summarize_forecast_window
from recommendations.schemas import RecommendationResponse
from supply_chain.sourcing import SourcingDecision, SourcingEngine

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sourcing = SourcingEngine(db)

    async def create_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        horizon_days: int = 7,
        model_version: str | None = None,
    ) -> RecommendationResponse:
        product = await self._get_product(customer_id, product_id)
        inventory = await self._get_latest_inventory(customer_id, store_id, product_id)
        resolved_model_version = await self._resolve_model_version(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            requested_version=model_version,
        )
        forecasts = await self._get_forecasts(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            model_version=resolved_model_version,
            horizon_days=horizon_days,
        )
        if not forecasts:
            raise ValueError("no future forecasts available for recommendation generation")

        service_level = await self._get_service_level(customer_id, store_id, product_id)
        expected_order_qty = max(1, round(sum(float(row.forecasted_demand or 0.0) for row in forecasts)))
        sourcing = await self.sourcing.get_sourcing_strategy(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            quantity=expected_order_qty,
        )
        (
            lead_time_days,
            lead_time_variance,
            source_type,
            source_id,
            source_name,
            min_order_qty,
            cost_per_order,
        ) = await self._resolve_supply_context(product=product, sourcing=sourcing)
        forecast_summary = summarize_forecast_window(forecasts, lead_time_days=round_lead_time_days(lead_time_days))

        store = await self.db.get(Store, store_id)
        cluster_tier = store.cluster_tier if store and store.cluster_tier is not None else 1
        cluster_multiplier = get_cluster_multipliers().get(cluster_tier, 1.0)

        supplier = None
        if source_type == "vendor_direct" and source_id is not None:
            supplier = await self.db.get(Supplier, source_id)
        elif product.supplier_id:
            supplier = await self.db.get(Supplier, product.supplier_id)

        vendor_reliability = supplier.reliability_score if supplier and supplier.reliability_score is not None else 0.95
        reliability_multiplier = get_reliability_multiplier(vendor_reliability)
        z_score = get_z_score(service_level)
        demand_component = lead_time_days * (forecast_summary.demand_std_dev**2)
        lead_time_component = (forecast_summary.avg_daily_demand**2) * (lead_time_variance**2)
        combined_std = math.sqrt(demand_component + lead_time_component)
        safety_stock = max(1, round(z_score * combined_std * reliability_multiplier * cluster_multiplier))
        reorder_point = max(1, round(forecast_summary.avg_daily_demand * lead_time_days + safety_stock))

        holding_cost_annual = self._resolve_holding_cost_annual(product)
        annual_demand = forecast_summary.avg_daily_demand * 365
        economic_order_qty = max(
            InventoryOptimizer._calculate_eoq(annual_demand, cost_per_order, holding_cost_annual),
            max(1, min_order_qty),
        )

        quantity_available = inventory.quantity_available if inventory else 0
        quantity_on_order = inventory.quantity_on_order if inventory else 0
        inventory_position = compute_inventory_position(quantity_available, quantity_on_order)
        recommended_quantity = compute_recommended_quantity(
            inventory_position=inventory_position,
            reorder_point=reorder_point,
            economic_order_qty=economic_order_qty,
            min_order_qty=min_order_qty,
        )

        no_order_stockout_risk = classify_no_order_stockout_risk(
            inventory_position=inventory_position,
            lead_time_demand_mean=forecast_summary.lead_time_demand_mean,
            lead_time_demand_upper=forecast_summary.lead_time_demand_upper or forecast_summary.lead_time_demand_mean,
        )
        order_overstock_risk = classify_order_overstock_risk(
            inventory_position=inventory_position,
            recommended_quantity=recommended_quantity,
            horizon_demand_mean=forecast_summary.horizon_demand_mean,
            horizon_demand_lower=forecast_summary.horizon_demand_lower or forecast_summary.horizon_demand_mean,
            safety_stock=safety_stock,
            economic_order_qty=economic_order_qty,
        )

        model_metadata = self._load_model_metadata(resolved_model_version)
        interval_method = model_metadata.get("interval_method")
        calibration_status = model_metadata.get("calibration_status")
        interval_coverage = model_metadata.get("interval_coverage")
        estimated_unit_cost = float(product.unit_cost) if product.unit_cost is not None else None
        estimated_total_cost = estimate_total_cost(
            recommended_quantity=recommended_quantity,
            unit_cost=estimated_unit_cost,
        )

        rationale = {
            "source_name": source_name,
            "forecast_start_date": forecast_summary.start_date.isoformat(),
            "forecast_end_date": forecast_summary.end_date.isoformat(),
            "horizon_demand_mean": forecast_summary.horizon_demand_mean,
            "horizon_demand_lower": forecast_summary.horizon_demand_lower,
            "horizon_demand_upper": forecast_summary.horizon_demand_upper,
            "lead_time_demand_mean": forecast_summary.lead_time_demand_mean,
            "lead_time_demand_upper": forecast_summary.lead_time_demand_upper,
            "interval_coverage": interval_coverage,
            "cluster_tier": cluster_tier,
            "cluster_multiplier": cluster_multiplier,
            "vendor_reliability": vendor_reliability,
            "reliability_multiplier": reliability_multiplier,
            "holding_cost_annual": round(holding_cost_annual, 4),
            "cost_per_order": cost_per_order,
            "min_order_qty": min_order_qty,
            "forecast_row_count": len(forecasts),
        }

        recommendation = ReplenishmentRecommendation(
            customer_id=customer_id,
            store_id=store_id,
            product_id=product_id,
            supplier_id=product.supplier_id,
            status="open",
            forecast_model_version=resolved_model_version,
            policy_version=POLICY_VERSION,
            horizon_days=horizon_days,
            recommended_quantity=recommended_quantity,
            quantity_available=quantity_available,
            quantity_on_order=quantity_on_order,
            inventory_position=inventory_position,
            reorder_point=reorder_point,
            safety_stock=safety_stock,
            economic_order_qty=economic_order_qty,
            lead_time_days=round_lead_time_days(lead_time_days),
            service_level=service_level,
            estimated_unit_cost=estimated_unit_cost,
            estimated_total_cost=estimated_total_cost,
            source_type=source_type,
            source_id=source_id,
            interval_method=interval_method,
            calibration_status=calibration_status,
            no_order_stockout_risk=no_order_stockout_risk,
            order_overstock_risk=order_overstock_risk,
            recommendation_rationale=rationale,
            created_at=datetime.utcnow(),
        )
        self.db.add(recommendation)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(recommendation)

        return self._to_response(
            recommendation,
            source_name=source_name,
            forecast_start_date=forecast_summary.start_date,
            forecast_end_date=forecast_summary.end_date,
            horizon_demand_mean=forecast_summary.horizon_demand_mean,
            horizon_demand_lower=forecast_summary.horizon_demand_lower,
            horizon_demand_upper=forecast_summary.horizon_demand_upper,
            lead_time_demand_mean=forecast_summary.lead_time_demand_mean,
            lead_time_demand_upper=forecast_summary.lead_time_demand_upper,
            interval_coverage=interval_coverage,
        )

    async def list_queue(
        self,
        *,
        customer_id: uuid.UUID,
        status: str = "open",
        limit: int = 50,
    ) -> list[RecommendationResponse]:
        result = await self.db.execute(
            select(ReplenishmentRecommendation)
            .where(
                ReplenishmentRecommendation.customer_id == customer_id,
                ReplenishmentRecommendation.status == status,
            )
            .order_by(ReplenishmentRecommendation.created_at.desc())
            .limit(limit)
        )
        return [self._to_response_from_record(row) for row in result.scalars().all()]

    async def generate_queue(
        self,
        *,
        customer_id: uuid.UUID,
        horizon_days: int = 7,
        model_version: str | None = None,
    ) -> dict[str, object]:
        start_date = datetime.utcnow().date()
        end_date = start_date + timedelta(days=max(1, horizon_days) - 1)

        forecast_pairs_query = (
            select(DemandForecast.store_id, DemandForecast.product_id)
            .where(
                DemandForecast.customer_id == customer_id,
                DemandForecast.forecast_date >= start_date,
                DemandForecast.forecast_date <= end_date,
            )
            .distinct()
            .order_by(DemandForecast.store_id.asc(), DemandForecast.product_id.asc())
        )
        if model_version:
            forecast_pairs_query = forecast_pairs_query.where(DemandForecast.model_version == model_version)

        candidate_pairs = list((await self.db.execute(forecast_pairs_query)).all())

        open_rows = (
            await self.db.execute(
                select(
                    ReplenishmentRecommendation.store_id,
                    ReplenishmentRecommendation.product_id,
                ).where(
                    ReplenishmentRecommendation.customer_id == customer_id,
                    ReplenishmentRecommendation.status == "open",
                )
            )
        ).all()
        open_pairs = {(row.store_id, row.product_id) for row in open_rows}

        generated_count = 0
        skipped_reasons: dict[str, int] = {}

        for pair in candidate_pairs:
            pair_key = (pair.store_id, pair.product_id)
            if pair_key in open_pairs:
                skipped_reasons["open_recommendation_exists"] = skipped_reasons.get("open_recommendation_exists", 0) + 1
                continue

            try:
                await self.create_recommendation(
                    customer_id=customer_id,
                    store_id=pair.store_id,
                    product_id=pair.product_id,
                    horizon_days=horizon_days,
                    model_version=model_version,
                )
                generated_count += 1
                open_pairs.add(pair_key)
            except ValueError as exc:
                reason = str(exc).strip().lower().replace(" ", "_")
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

        open_queue_count = await self.db.scalar(
            select(func.count(ReplenishmentRecommendation.recommendation_id)).where(
                ReplenishmentRecommendation.customer_id == customer_id,
                ReplenishmentRecommendation.status == "open",
            )
        )

        return {
            "as_of_date": start_date.isoformat(),
            "horizon_days": horizon_days,
            "model_version": model_version,
            "candidate_pairs": len(candidate_pairs),
            "generated_count": generated_count,
            "skipped_count": sum(skipped_reasons.values()),
            "skipped_reasons": skipped_reasons,
            "open_queue_count": int(open_queue_count or 0),
        }

    async def get_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
    ) -> RecommendationResponse:
        record = await self._require_recommendation(customer_id=customer_id, recommendation_id=recommendation_id)
        return self._to_response_from_record(record)

    async def accept_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        actor: str,
        reason_code: str | None = None,
        notes: str | None = None,
    ) -> RecommendationResponse:
        record = await self._require_open_recommendation(customer_id=customer_id, recommendation_id=recommendation_id)
        purchase_order = self._build_purchase_order(record=record, quantity=record.recommended_quantity)
        self.db.add(purchase_order)
        await self.db.flush()
        self.db.add(
            PODecision(
                customer_id=record.customer_id,
                po_id=purchase_order.po_id,
                decision_type="approved",
                original_qty=record.recommended_quantity,
                final_qty=record.recommended_quantity,
                reason_code=reason_code,
                notes=notes,
                decided_by=actor,
            )
        )
        record.status = "accepted"
        record.linked_po_id = purchase_order.po_id
        self._append_decision_metadata(
            record, decision_type="accepted", actor=actor, reason_code=reason_code, notes=notes
        )
        await self.db.commit()
        await self.db.refresh(record)
        return self._to_response_from_record(record)

    async def edit_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        quantity: int,
        actor: str,
        reason_code: str,
        notes: str | None = None,
    ) -> RecommendationResponse:
        record = await self._require_open_recommendation(customer_id=customer_id, recommendation_id=recommendation_id)
        purchase_order = self._build_purchase_order(record=record, quantity=quantity)
        self.db.add(purchase_order)
        await self.db.flush()
        self.db.add(
            PODecision(
                customer_id=record.customer_id,
                po_id=purchase_order.po_id,
                decision_type="edited",
                original_qty=record.recommended_quantity,
                final_qty=quantity,
                reason_code=reason_code,
                notes=notes,
                decided_by=actor,
            )
        )
        record.status = "edited"
        record.linked_po_id = purchase_order.po_id
        self._append_decision_metadata(
            record, decision_type="edited", actor=actor, reason_code=reason_code, notes=notes
        )
        await self.db.commit()
        await self.db.refresh(record)
        return self._to_response_from_record(record)

    async def reject_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        actor: str,
        reason_code: str,
        notes: str | None = None,
    ) -> RecommendationResponse:
        record = await self._require_open_recommendation(customer_id=customer_id, recommendation_id=recommendation_id)
        record.status = "rejected"
        self._append_decision_metadata(
            record, decision_type="rejected", actor=actor, reason_code=reason_code, notes=notes
        )
        await self.db.commit()
        await self.db.refresh(record)
        return self._to_response_from_record(record)

    async def _get_product(self, customer_id: uuid.UUID, product_id: uuid.UUID) -> Product:
        result = await self.db.execute(
            select(Product).where(
                Product.customer_id == customer_id,
                Product.product_id == product_id,
                Product.status == "active",
            )
        )
        product = result.scalar_one_or_none()
        if product is None:
            raise ValueError("active product not found")
        return product

    async def _get_latest_inventory(
        self,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> InventoryLevel | None:
        result = await self.db.execute(
            select(InventoryLevel)
            .where(
                InventoryLevel.customer_id == customer_id,
                InventoryLevel.store_id == store_id,
                InventoryLevel.product_id == product_id,
            )
            .order_by(desc(InventoryLevel.timestamp))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_service_level(self, customer_id: uuid.UUID, store_id: uuid.UUID, product_id: uuid.UUID) -> float:
        result = await self.db.execute(
            select(ReorderPoint.service_level).where(
                ReorderPoint.customer_id == customer_id,
                ReorderPoint.store_id == store_id,
                ReorderPoint.product_id == product_id,
            )
        )
        service_level = result.scalar_one_or_none()
        return float(service_level) if service_level is not None else get_default_service_level()

    async def _resolve_model_version(
        self,
        *,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        requested_version: str | None,
    ) -> str:
        if requested_version:
            return requested_version

        champion_path = MODELS_DIR / "champion.json"
        if champion_path.exists():
            payload = json.loads(champion_path.read_text())
            champion_version = payload.get("version")
            if champion_version:
                exists = await self.db.execute(
                    select(DemandForecast.forecast_id)
                    .where(
                        DemandForecast.customer_id == customer_id,
                        DemandForecast.store_id == store_id,
                        DemandForecast.product_id == product_id,
                        DemandForecast.model_version == champion_version,
                        DemandForecast.forecast_date >= datetime.utcnow().date(),
                    )
                    .limit(1)
                )
                if exists.scalar_one_or_none() is not None:
                    return champion_version

        result = await self.db.execute(
            select(DemandForecast.model_version)
            .where(
                DemandForecast.customer_id == customer_id,
                DemandForecast.store_id == store_id,
                DemandForecast.product_id == product_id,
                DemandForecast.forecast_date >= datetime.utcnow().date(),
            )
            .order_by(desc(DemandForecast.created_at))
            .limit(1)
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise ValueError("no forecast model version available")
        return version

    async def _get_forecasts(
        self,
        *,
        customer_id: uuid.UUID,
        store_id: uuid.UUID,
        product_id: uuid.UUID,
        model_version: str,
        horizon_days: int,
    ) -> list[DemandForecast]:
        start_date = datetime.utcnow().date()
        end_date = start_date + timedelta(days=max(1, horizon_days) - 1)
        result = await self.db.execute(
            select(DemandForecast)
            .where(
                DemandForecast.customer_id == customer_id,
                DemandForecast.store_id == store_id,
                DemandForecast.product_id == product_id,
                DemandForecast.model_version == model_version,
                DemandForecast.forecast_date >= start_date,
                DemandForecast.forecast_date <= end_date,
            )
            .order_by(DemandForecast.forecast_date.asc())
        )
        return list(result.scalars().all())

    async def _resolve_supply_context(
        self,
        *,
        product: Product,
        sourcing: SourcingDecision | None,
    ) -> tuple[float, float, str | None, uuid.UUID | None, str | None, int, float]:
        if sourcing is not None:
            return (
                float(sourcing.lead_time.mean_days),
                float(sourcing.lead_time.variance_days or 0.0),
                sourcing.source_type,
                sourcing.source_id,
                sourcing.source_name,
                max(1, int(sourcing.min_order_qty or 1)),
                float(sourcing.cost_per_order or 0.0),
            )

        supplier = await self.db.get(Supplier, product.supplier_id) if product.supplier_id else None
        return (
            float(supplier.lead_time_days if supplier else 7.0),
            float(supplier.lead_time_variance if supplier and supplier.lead_time_variance is not None else 1.0),
            "vendor_direct" if supplier else None,
            supplier.supplier_id if supplier else None,
            supplier.name if supplier else None,
            max(1, int(supplier.min_order_quantity if supplier and supplier.min_order_quantity else 1)),
            float(supplier.cost_per_order if supplier and supplier.cost_per_order is not None else 0.0),
        )

    def _resolve_holding_cost_annual(self, product: Product) -> float:
        if product.holding_cost_per_unit_per_day is not None:
            return float(product.holding_cost_per_unit_per_day) * 365
        if product.unit_cost is not None:
            return float(product.unit_cost) * 0.25
        return 5.0

    def _load_model_metadata(self, model_version: str) -> dict:
        metadata_path = MODELS_DIR / model_version / "metadata.json"
        if metadata_path.exists():
            return json.loads(metadata_path.read_text())
        return {}

    async def _require_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
    ) -> ReplenishmentRecommendation:
        result = await self.db.execute(
            select(ReplenishmentRecommendation).where(
                ReplenishmentRecommendation.customer_id == customer_id,
                ReplenishmentRecommendation.recommendation_id == recommendation_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise ValueError("recommendation not found")
        return record

    async def _require_open_recommendation(
        self,
        *,
        customer_id: uuid.UUID,
        recommendation_id: uuid.UUID,
    ) -> ReplenishmentRecommendation:
        record = await self._require_recommendation(customer_id=customer_id, recommendation_id=recommendation_id)
        if record.status != "open":
            raise ValueError(f"recommendation is not open: {record.status}")
        return record

    def _build_purchase_order(self, *, record: ReplenishmentRecommendation, quantity: int) -> PurchaseOrder:
        expected_delivery = date.today() + timedelta(days=record.lead_time_days)
        return PurchaseOrder(
            customer_id=record.customer_id,
            store_id=record.store_id,
            product_id=record.product_id,
            supplier_id=record.supplier_id,
            quantity=quantity,
            estimated_cost=estimate_total_cost(recommended_quantity=quantity, unit_cost=record.estimated_unit_cost),
            status="approved",
            ordered_at=datetime.utcnow(),
            expected_delivery=expected_delivery,
            source_type=record.source_type,
            source_id=record.source_id,
            promised_delivery_date=expected_delivery,
        )

    def _append_decision_metadata(
        self,
        record: ReplenishmentRecommendation,
        *,
        decision_type: str,
        actor: str,
        reason_code: str | None,
        notes: str | None,
    ) -> None:
        rationale = dict(record.recommendation_rationale or {})
        rationale["decision"] = {
            "decision_type": decision_type,
            "actor": actor,
            "reason_code": reason_code,
            "notes": notes,
            "decided_at": datetime.utcnow().isoformat(),
        }
        record.recommendation_rationale = rationale

    def _to_response_from_record(self, record: ReplenishmentRecommendation) -> RecommendationResponse:
        rationale = record.recommendation_rationale or {}
        return self._to_response(
            record,
            source_name=rationale.get("source_name"),
            forecast_start_date=self._parse_iso_date(rationale.get("forecast_start_date"), record.created_at.date()),
            forecast_end_date=self._parse_iso_date(rationale.get("forecast_end_date"), record.created_at.date()),
            horizon_demand_mean=float(rationale.get("horizon_demand_mean") or 0.0),
            horizon_demand_lower=self._optional_float(rationale.get("horizon_demand_lower")),
            horizon_demand_upper=self._optional_float(rationale.get("horizon_demand_upper")),
            lead_time_demand_mean=float(rationale.get("lead_time_demand_mean") or 0.0),
            lead_time_demand_upper=self._optional_float(rationale.get("lead_time_demand_upper")),
            interval_coverage=self._optional_float(rationale.get("interval_coverage")),
        )

    def _parse_iso_date(self, value, fallback: date) -> date:
        if not value:
            return fallback
        return date.fromisoformat(value)

    def _optional_float(self, value) -> float | None:
        if value is None:
            return None
        return float(value)

    def _to_response(
        self,
        recommendation: ReplenishmentRecommendation,
        *,
        source_name: str | None,
        forecast_start_date,
        forecast_end_date,
        horizon_demand_mean: float,
        horizon_demand_lower: float | None,
        horizon_demand_upper: float | None,
        lead_time_demand_mean: float,
        lead_time_demand_upper: float | None,
        interval_coverage: float | None,
    ) -> RecommendationResponse:
        return RecommendationResponse(
            recommendation_id=recommendation.recommendation_id,
            customer_id=recommendation.customer_id,
            store_id=recommendation.store_id,
            product_id=recommendation.product_id,
            supplier_id=recommendation.supplier_id,
            linked_po_id=recommendation.linked_po_id,
            status=recommendation.status,
            forecast_model_version=recommendation.forecast_model_version,
            policy_version=recommendation.policy_version,
            horizon_days=recommendation.horizon_days,
            forecast_start_date=forecast_start_date,
            forecast_end_date=forecast_end_date,
            recommended_quantity=recommendation.recommended_quantity,
            quantity_available=recommendation.quantity_available,
            quantity_on_order=recommendation.quantity_on_order,
            inventory_position=recommendation.inventory_position,
            reorder_point=recommendation.reorder_point,
            safety_stock=recommendation.safety_stock,
            economic_order_qty=recommendation.economic_order_qty,
            lead_time_days=recommendation.lead_time_days,
            service_level=recommendation.service_level,
            estimated_unit_cost=recommendation.estimated_unit_cost,
            estimated_total_cost=recommendation.estimated_total_cost,
            source_type=recommendation.source_type,
            source_id=recommendation.source_id,
            source_name=source_name,
            horizon_demand_mean=horizon_demand_mean,
            horizon_demand_lower=horizon_demand_lower,
            horizon_demand_upper=horizon_demand_upper,
            lead_time_demand_mean=lead_time_demand_mean,
            lead_time_demand_upper=lead_time_demand_upper,
            interval_method=recommendation.interval_method,
            calibration_status=recommendation.calibration_status,
            interval_coverage=interval_coverage,
            no_order_stockout_risk=recommendation.no_order_stockout_risk,
            order_overstock_risk=recommendation.order_overstock_risk,
            recommendation_rationale=recommendation.recommendation_rationale,
            created_at=recommendation.created_at,
        )
