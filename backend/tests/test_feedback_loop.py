"""
Tests for ML Feedback Loop — PO rejection decisions to ML features.

Covers:
  - Empty result when no decisions exist
  - Rejection rate and trust score calculation
  - Average quantity adjustment percentage
  - Multiple store/product combinations are grouped correctly
  - enrich_features_with_feedback: neutral defaults when feedback is empty
  - enrich_features_with_feedback: merge populates correct values
  - enrich_features_with_feedback: products without history get neutral defaults
"""

import uuid
from datetime import datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import select

from db.models import Customer, PODecision, Product, PurchaseOrder, Store, Supplier
from ml.feedback_loop import enrich_features_with_feedback, get_feedback_features

CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"


# ── Helpers ────────────────────────────────────────────────────────────────


async def _seed_base_entities(db):
    """Insert Customer, Supplier, Store, and Product, return their IDs."""
    customer_id = uuid.UUID(CUSTOMER_ID)

    customer = Customer(
        customer_id=customer_id,
        name="Feedback Test Grocers",
        email="feedback@testgrocers.com",
        plan="professional",
    )
    db.add(customer)
    await db.flush()

    supplier = Supplier(
        customer_id=customer_id,
        name="Feedback Distributor",
        contact_email="fb@dist.com",
        lead_time_days=3,
    )
    db.add(supplier)
    await db.flush()

    store = Store(
        customer_id=customer_id,
        name="Feedback Store",
        city="Chicago",
        state="IL",
        zip_code="60601",
    )
    db.add(store)
    await db.flush()

    product = Product(
        customer_id=customer_id,
        sku="FB-SKU-001",
        name="Feedback Product",
        category="Snacks",
        unit_cost=1.00,
        unit_price=2.50,
        supplier_id=supplier.supplier_id,
    )
    db.add(product)
    await db.flush()

    return customer_id, store.store_id, product.product_id, supplier.supplier_id


async def _make_po_with_decision(db, customer_id, store_id, product_id, supplier_id,
                                  decision_type, original_qty, final_qty,
                                  decided_at=None):
    """Create a PurchaseOrder and an associated PODecision."""
    po = PurchaseOrder(
        customer_id=customer_id,
        store_id=store_id,
        product_id=product_id,
        supplier_id=supplier_id,
        quantity=original_qty,
        status="suggested",
        source_type="vendor_direct",
    )
    db.add(po)
    await db.flush()

    decision = PODecision(
        customer_id=customer_id,
        po_id=po.po_id,
        decision_type=decision_type,
        original_qty=original_qty,
        final_qty=final_qty,
        decided_at=decided_at or datetime.utcnow(),
    )
    db.add(decision)
    await db.flush()

    return po, decision


# ── get_feedback_features ──────────────────────────────────────────────────


class TestGetFeedbackFeaturesEmpty:
    async def test_returns_empty_dataframe_when_no_decisions_exist(self, test_db):
        await _seed_base_entities(test_db)

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert df.empty
        assert list(df.columns) == [
            "store_id",
            "product_id",
            "rejection_rate_30d",
            "avg_qty_adjustment_pct",
            "forecast_trust_score",
        ]

    async def test_returns_empty_dataframe_when_decisions_are_outside_lookback_window(
        self, test_db
    ):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # Decision that is 60 days old (outside default 30-day window)
        old_date = datetime.utcnow() - timedelta(days=60)
        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "rejected", 100, 0, decided_at=old_date
        )

        df = await get_feedback_features(test_db, CUSTOMER_ID, lookback_days=30)

        assert df.empty


class TestGetFeedbackFeaturesCalculations:
    async def test_all_rejections_produces_zero_trust_score(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        for _ in range(3):
            await _make_po_with_decision(
                test_db, customer_id, store_id, product_id, supplier_id,
                "rejected", 50, 0
            )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["rejection_rate_30d"] == 1.0
        assert row["forecast_trust_score"] == 0.0

    async def test_all_approvals_produces_full_trust_score(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        for _ in range(4):
            await _make_po_with_decision(
                test_db, customer_id, store_id, product_id, supplier_id,
                "approved", 50, 50
            )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["rejection_rate_30d"] == 0.0
        assert row["forecast_trust_score"] == 1.0

    async def test_mixed_decisions_produce_correct_rejection_rate(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # 2 rejected, 2 approved → 50% rejection rate
        for _ in range(2):
            await _make_po_with_decision(
                test_db, customer_id, store_id, product_id, supplier_id,
                "rejected", 40, 0
            )
        for _ in range(2):
            await _make_po_with_decision(
                test_db, customer_id, store_id, product_id, supplier_id,
                "approved", 40, 40
            )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 1
        row = df.iloc[0]
        assert row["rejection_rate_30d"] == 0.5
        assert row["forecast_trust_score"] == 0.5

    async def test_qty_adjustment_pct_is_correct_when_quantity_is_edited_upward(
        self, test_db
    ):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # Original qty 100 → final qty 150: +50%
        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "edited", 100, 150
        )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 1
        assert df.iloc[0]["avg_qty_adjustment_pct"] == 50.0

    async def test_qty_adjustment_pct_is_correct_when_quantity_is_edited_downward(
        self, test_db
    ):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # Original qty 200 → final qty 100: -50%
        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "edited", 200, 100
        )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 1
        assert df.iloc[0]["avg_qty_adjustment_pct"] == -50.0

    async def test_features_grouped_by_store_and_product(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # Second product for the same store
        product2 = Product(
            customer_id=customer_id,
            sku="FB-SKU-002",
            name="Second Feedback Product",
            category="Snacks",
            unit_cost=2.00,
            unit_price=4.00,
            supplier_id=supplier_id,
        )
        test_db.add(product2)
        await test_db.flush()

        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "rejected", 60, 0
        )
        await _make_po_with_decision(
            test_db, customer_id, store_id, product2.product_id, supplier_id,
            "approved", 60, 60
        )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert len(df) == 2
        product_ids = set(df["product_id"].tolist())
        assert str(product_id) in product_ids
        assert str(product2.product_id) in product_ids

    async def test_respects_custom_lookback_days_parameter(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        # Decision 10 days ago — within a 15-day window but outside a 7-day window
        recent = datetime.utcnow() - timedelta(days=10)
        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "rejected", 50, 0, decided_at=recent
        )

        df_7 = await get_feedback_features(test_db, CUSTOMER_ID, lookback_days=7)
        df_15 = await get_feedback_features(test_db, CUSTOMER_ID, lookback_days=15)

        assert df_7.empty
        assert len(df_15) == 1

    async def test_result_store_id_and_product_id_are_strings(self, test_db):
        customer_id, store_id, product_id, supplier_id = await _seed_base_entities(test_db)

        await _make_po_with_decision(
            test_db, customer_id, store_id, product_id, supplier_id,
            "approved", 30, 30
        )

        df = await get_feedback_features(test_db, CUSTOMER_ID)

        assert isinstance(df.iloc[0]["store_id"], str)
        assert isinstance(df.iloc[0]["product_id"], str)


# ── enrich_features_with_feedback ─────────────────────────────────────────


class TestEnrichFeaturesWithFeedback:
    def test_empty_feedback_adds_neutral_defaults_to_all_rows(self):
        features_df = pd.DataFrame(
            [
                {"store_id": "s1", "product_id": "p1", "demand": 10.0},
                {"store_id": "s1", "product_id": "p2", "demand": 5.0},
            ]
        )
        feedback_df = pd.DataFrame(
            columns=[
                "store_id",
                "product_id",
                "rejection_rate_30d",
                "avg_qty_adjustment_pct",
                "forecast_trust_score",
            ]
        )

        result = enrich_features_with_feedback(features_df, feedback_df)

        assert list(result["rejection_rate_30d"]) == [0.0, 0.0]
        assert list(result["avg_qty_adjustment_pct"]) == [0.0, 0.0]
        assert list(result["forecast_trust_score"]) == [1.0, 1.0]

    def test_matched_rows_get_actual_feedback_values(self):
        features_df = pd.DataFrame(
            [{"store_id": "s1", "product_id": "p1"}]
        )
        feedback_df = pd.DataFrame(
            [
                {
                    "store_id": "s1",
                    "product_id": "p1",
                    "rejection_rate_30d": 0.4,
                    "avg_qty_adjustment_pct": -10.0,
                    "forecast_trust_score": 0.6,
                }
            ]
        )

        result = enrich_features_with_feedback(features_df, feedback_df)

        assert result.iloc[0]["rejection_rate_30d"] == 0.4
        assert result.iloc[0]["avg_qty_adjustment_pct"] == -10.0
        assert result.iloc[0]["forecast_trust_score"] == 0.6

    def test_unmatched_rows_get_neutral_defaults_when_feedback_is_partial(self):
        features_df = pd.DataFrame(
            [
                {"store_id": "s1", "product_id": "p1"},
                {"store_id": "s1", "product_id": "p2"},  # no feedback for p2
            ]
        )
        feedback_df = pd.DataFrame(
            [
                {
                    "store_id": "s1",
                    "product_id": "p1",
                    "rejection_rate_30d": 0.8,
                    "avg_qty_adjustment_pct": 25.0,
                    "forecast_trust_score": 0.2,
                }
            ]
        )

        result = enrich_features_with_feedback(features_df, feedback_df)

        p2_row = result[result["product_id"] == "p2"].iloc[0]
        assert p2_row["rejection_rate_30d"] == 0.0
        assert p2_row["avg_qty_adjustment_pct"] == 0.0
        assert p2_row["forecast_trust_score"] == 1.0

    def test_original_feature_columns_are_preserved_after_merge(self):
        features_df = pd.DataFrame(
            [{"store_id": "s1", "product_id": "p1", "demand_forecast": 42.0}]
        )
        feedback_df = pd.DataFrame(
            [
                {
                    "store_id": "s1",
                    "product_id": "p1",
                    "rejection_rate_30d": 0.1,
                    "avg_qty_adjustment_pct": 5.0,
                    "forecast_trust_score": 0.9,
                }
            ]
        )

        result = enrich_features_with_feedback(features_df, feedback_df)

        assert "demand_forecast" in result.columns
        assert result.iloc[0]["demand_forecast"] == 42.0

    def test_row_count_is_unchanged_after_left_join(self):
        features_df = pd.DataFrame(
            [
                {"store_id": "s1", "product_id": f"p{i}"}
                for i in range(5)
            ]
        )
        feedback_df = pd.DataFrame(
            [
                {
                    "store_id": "s1",
                    "product_id": "p0",
                    "rejection_rate_30d": 0.5,
                    "avg_qty_adjustment_pct": 0.0,
                    "forecast_trust_score": 0.5,
                }
            ]
        )

        result = enrich_features_with_feedback(features_df, feedback_df)

        assert len(result) == 5
