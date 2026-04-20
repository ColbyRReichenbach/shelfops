import uuid
from datetime import datetime

import pytest
from sqlalchemy import func, select

from db.models import PODecision, PurchaseOrder, ReplenishmentRecommendation
from recommendations.service import RecommendationService
from tests.test_recommendation_service import _seed_recommendation_fixture

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _create_open_recommendation(db):
    store, product, _supplier = await _seed_recommendation_fixture(db)
    service = RecommendationService(db)
    recommendation = await service.create_recommendation(
        customer_id=CUSTOMER_ID,
        store_id=store.store_id,
        product_id=product.product_id,
        horizon_days=7,
        model_version="v3",
    )
    return recommendation


@pytest.mark.asyncio
class TestReplenishmentAPI:
    async def test_list_queue_returns_buyer_ready_cards(self, client, test_db):
        recommendation = await _create_open_recommendation(test_db)

        response = await client.get("/api/v1/replenishment/queue")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["recommendation_id"] == str(recommendation.recommendation_id)
        assert data[0]["forecast_model_version"] == "v3"
        assert data[0]["policy_version"] == "replenishment_v1"
        assert data[0]["interval_method"] == "split_conformal"
        assert data[0]["recommended_quantity"] == 46
        assert data[0]["no_order_stockout_risk"] == "high"
        assert data[0]["order_overstock_risk"] == "high"

    async def test_get_recommendation_detail(self, client, test_db):
        recommendation = await _create_open_recommendation(test_db)

        response = await client.get(f"/api/v1/replenishment/recommendations/{recommendation.recommendation_id}")

        assert response.status_code == 200
        assert response.json()["recommendation_id"] == str(recommendation.recommendation_id)

    async def test_generate_queue_creates_open_recommendations(self, client, test_db):
        await _seed_recommendation_fixture(test_db)

        response = await client.post("/api/v1/replenishment/generate", json={})

        assert response.status_code == 200
        payload = response.json()
        assert payload["candidate_pairs"] == 1
        assert payload["generated_count"] == 1
        assert payload["skipped_count"] == 0
        assert payload["open_queue_count"] == 1

    async def test_generate_queue_skips_existing_open_recommendations(self, client, test_db):
        await _create_open_recommendation(test_db)

        response = await client.post("/api/v1/replenishment/generate", json={})

        assert response.status_code == 200
        payload = response.json()
        assert payload["candidate_pairs"] == 1
        assert payload["generated_count"] == 0
        assert payload["skipped_count"] == 1
        assert payload["skipped_reasons"]["open_recommendation_exists"] == 1
        assert payload["open_queue_count"] == 1

    async def test_accept_recommendation_creates_linked_purchase_order(self, client, test_db):
        recommendation = await _create_open_recommendation(test_db)

        response = await client.post(
            f"/api/v1/replenishment/recommendations/{recommendation.recommendation_id}/accept",
            json={"notes": "Looks correct"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "accepted"
        assert payload["linked_po_id"] is not None

        po_result = await test_db.execute(select(PurchaseOrder))
        purchase_order = po_result.scalar_one()
        assert purchase_order.quantity == 46
        assert purchase_order.status == "approved"

        decision_result = await test_db.execute(select(PODecision))
        decision = decision_result.scalar_one()
        assert decision.decision_type == "approved"
        assert decision.final_qty == 46

    async def test_edit_recommendation_creates_edited_purchase_order(self, client, test_db):
        recommendation = await _create_open_recommendation(test_db)

        response = await client.post(
            f"/api/v1/replenishment/recommendations/{recommendation.recommendation_id}/edit",
            json={"quantity": 30, "reason_code": "budget_constraint", "notes": "Trim order size"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "edited"
        assert payload["linked_po_id"] is not None

        po_result = await test_db.execute(select(PurchaseOrder))
        purchase_order = po_result.scalar_one()
        assert purchase_order.quantity == 30

        decision_result = await test_db.execute(select(PODecision))
        decision = decision_result.scalar_one()
        assert decision.decision_type == "edited"
        assert decision.reason_code == "budget_constraint"

    async def test_reject_recommendation_updates_status_without_creating_po(self, client, test_db):
        recommendation = await _create_open_recommendation(test_db)

        response = await client.post(
            f"/api/v1/replenishment/recommendations/{recommendation.recommendation_id}/reject",
            json={"reason_code": "manual_ordered_elsewhere", "notes": "Handled outside ShelfOps"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "rejected"
        assert payload["linked_po_id"] is None

        po_count = await test_db.scalar(select(func.count(PurchaseOrder.po_id)))
        assert po_count == 0

        recommendation_row = await test_db.get(ReplenishmentRecommendation, recommendation.recommendation_id)
        assert recommendation_row.status == "rejected"
        assert recommendation_row.recommendation_rationale["decision"]["reason_code"] == "manual_ordered_elsewhere"
