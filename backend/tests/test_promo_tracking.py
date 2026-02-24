"""
Tests for Promotion Effectiveness Tracker — actual vs expected lift.

Notes on known schema mismatches in retail/promo_tracking.py:
  1. Transaction.transaction_date does not exist; the column is Transaction.timestamp.
  2. PromotionResult is constructed with keyword arguments (baseline_daily_avg,
     promo_daily_avg, expected_lift, variance_pct, needs_review) that do not exist
     on the ORM model; the model uses baseline_daily_sales and promo_daily_sales,
     and has no expected_lift, variance_pct, or needs_review columns.

These bugs mean the full DB-insert path will raise an AttributeError.
Tests that exercise the failing path are marked xfail with the reason above.
Tests that only exercise the filtering / query / summary-return logic are written
against the real test_db fixture.

Lift math is tested with a pure helper that mirrors the in-function arithmetic,
since the end-to-end function cannot write its result to the DB.

Covers:
  - Returns zero counts when no promotions match the window
  - Skips promotions without store_id or product_id
  - Skips promotions that already have a PromotionResult
  - Skips promotions with zero baseline (no pre-promo sales data)
  - Actual lift calculation: promo_avg / baseline_avg
  - Variance percentage: |actual - expected| / expected × 100
  - Flags promotions where variance > 30%
  - Promotions that ended outside the measurement window are excluded
"""

import uuid
from datetime import date, datetime, timedelta

import pytest

from db.models import Customer, Product, Promotion, PromotionResult, Store, Supplier, Transaction

CUSTOMER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
TODAY = date(2026, 2, 23)  # Matches project current date for deterministic tests


# ── Pure calculation helpers (mirrors promo_tracking.py arithmetic) ────────


def _compute_actual_lift(baseline_avg: float, promo_avg: float) -> float:
    return round(float(promo_avg) / float(baseline_avg), 3) if baseline_avg > 0 else 1.0


def _compute_variance_pct(actual_lift: float, expected_lift: float) -> float:
    return round(abs(actual_lift - expected_lift) / max(expected_lift, 0.01) * 100, 1)


# ── Fixtures / seed helpers ────────────────────────────────────────────────


async def _seed_base(db):
    customer = Customer(
        customer_id=CUSTOMER_ID,
        name="Promo Test Grocers",
        email="promo@testgrocers.com",
        plan="professional",
    )
    db.add(customer)
    await db.flush()

    supplier = Supplier(
        customer_id=CUSTOMER_ID,
        name="Promo Supplier",
        contact_email="promo@supplier.com",
        lead_time_days=4,
    )
    db.add(supplier)
    await db.flush()

    store = Store(
        customer_id=CUSTOMER_ID,
        name="Promo Store",
        city="Portland",
        state="OR",
        zip_code="97201",
    )
    db.add(store)
    await db.flush()

    product = Product(
        customer_id=CUSTOMER_ID,
        sku="PROMO-001",
        name="Promo Product",
        category="Snacks",
        unit_cost=1.20,
        unit_price=2.50,
        supplier_id=supplier.supplier_id,
    )
    db.add(product)
    await db.flush()

    return store, product


def _make_promo(store_id, product_id, start_date, end_date, expected_lift=1.5, status="completed"):
    return Promotion(
        customer_id=CUSTOMER_ID,
        store_id=store_id,
        product_id=product_id,
        name="Test Promo",
        discount_pct=0.10,
        start_date=start_date,
        end_date=end_date,
        expected_lift=expected_lift,
        status=status,
    )


# ── Lift math (pure, no DB) ────────────────────────────────────────────────


class TestActualLiftCalculation:
    def test_lift_is_ratio_of_promo_avg_to_baseline_avg(self):
        """1.8x promo average vs 1.0x baseline → lift = 1.8."""
        baseline = 10.0
        promo = 18.0
        assert _compute_actual_lift(baseline, promo) == 1.8

    def test_no_increase_produces_lift_of_one(self):
        """Same sales during and before promo → lift = 1.0."""
        assert _compute_actual_lift(10.0, 10.0) == 1.0

    def test_zero_baseline_returns_lift_of_one(self):
        """Zero baseline is guarded — returns 1.0 to avoid division by zero."""
        assert _compute_actual_lift(0.0, 20.0) == 1.0

    def test_lift_below_baseline_is_less_than_one(self):
        """Sales dropped during promo → lift < 1.0."""
        lift = _compute_actual_lift(20.0, 10.0)
        assert lift == 0.5

    def test_lift_is_rounded_to_three_decimal_places(self):
        """Result precision is 3 dp."""
        lift = _compute_actual_lift(3.0, 10.0)
        assert lift == round(10 / 3, 3)


class TestVariancePercentage:
    def test_variance_is_zero_when_actual_matches_expected(self):
        assert _compute_variance_pct(1.5, 1.5) == 0.0

    def test_variance_exceeds_30_pct_triggers_flag(self):
        """Actual 2.0 vs expected 1.5 → |2.0-1.5|/1.5 × 100 = 33.3%."""
        pct = _compute_variance_pct(2.0, 1.5)
        assert pct > 30.0

    def test_variance_under_30_pct_does_not_trigger_flag(self):
        """Actual 1.6 vs expected 1.5 → |1.6-1.5|/1.5 × 100 = 6.7%."""
        pct = _compute_variance_pct(1.6, 1.5)
        assert pct < 30.0

    def test_variance_pct_is_symmetric(self):
        """Variance should be the same whether actual is above or below expected."""
        over = _compute_variance_pct(2.0, 1.5)
        under = _compute_variance_pct(1.0, 1.5)
        assert over == under

    def test_variance_rounds_to_one_decimal_place(self):
        pct = _compute_variance_pct(1.8, 1.5)
        assert pct == round(abs(1.8 - 1.5) / 1.5 * 100, 1)


# ── DB-backed: promotion window filtering ─────────────────────────────────


class TestPromotionWindowFiltering:
    async def test_returns_zero_counts_when_no_promotions_in_window(self, test_db):
        """No promotions in the 7-14 day window → 0 evaluated."""
        from retail.promo_tracking import measure_promotion_effectiveness

        await _seed_base(test_db)

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["promotions_evaluated"] == 0
        assert summary["total_candidates"] == 0

    async def test_promotion_ending_yesterday_is_outside_window(self, test_db):
        """Promos must end ≥7 days ago to be measurable; yesterday is too recent."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        yesterday = TODAY - timedelta(days=1)

        promo = _make_promo(
            store.store_id,
            product.product_id,
            start_date=yesterday - timedelta(days=7),
            end_date=yesterday,
        )
        test_db.add(promo)
        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 0

    async def test_promotion_ending_more_than_lookback_days_ago_is_excluded(self, test_db):
        """Promo that ended 20 days ago is outside a 14-day lookback."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=20)

        promo = _make_promo(
            store.store_id,
            product.product_id,
            start_date=end_date - timedelta(days=7),
            end_date=end_date,
        )
        test_db.add(promo)
        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 0

    async def test_promotion_in_valid_window_is_counted_as_candidate(self, test_db):
        """A promo ending 10 days ago with a 14-day lookback is a valid candidate."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=10)

        promo = _make_promo(
            store.store_id,
            product.product_id,
            start_date=end_date - timedelta(days=7),
            end_date=end_date,
        )
        test_db.add(promo)
        await test_db.flush()

        # Will be a candidate but skipped because it has no Transaction data
        # (baseline_avg = 0 → skipped before the schema-breaking DB insert)
        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 1
        assert summary["promotions_evaluated"] == 0  # No baseline sales data


class TestPromotionSkipConditions:
    async def test_promotion_without_store_id_is_skipped(self, test_db):
        """Promotions missing store_id cannot compute store-level lift."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=10)

        promo = Promotion(
            customer_id=CUSTOMER_ID,
            store_id=None,  # No store
            product_id=product.product_id,
            name="No-Store Promo",
            discount_pct=0.10,
            start_date=end_date - timedelta(days=7),
            end_date=end_date,
            expected_lift=1.5,
            status="completed",
        )
        test_db.add(promo)
        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 1
        assert summary["promotions_evaluated"] == 0

    async def test_promotion_without_product_id_is_skipped(self, test_db):
        """Promotions missing product_id cannot compute product-level lift."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=10)

        promo = Promotion(
            customer_id=CUSTOMER_ID,
            store_id=store.store_id,
            product_id=None,  # No product
            name="No-Product Promo",
            discount_pct=0.10,
            start_date=end_date - timedelta(days=7),
            end_date=end_date,
            expected_lift=1.5,
            status="completed",
        )
        test_db.add(promo)
        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 1
        assert summary["promotions_evaluated"] == 0

    async def test_already_measured_promotion_is_skipped(self, test_db):
        """A promotion that already has a PromotionResult row is not re-measured."""
        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=10)

        promo = _make_promo(
            store.store_id,
            product.product_id,
            start_date=end_date - timedelta(days=7),
            end_date=end_date,
        )
        test_db.add(promo)
        await test_db.flush()

        # Pre-insert a PromotionResult to simulate already measured
        existing_result = PromotionResult(
            customer_id=CUSTOMER_ID,
            promotion_id=promo.promotion_id,
            store_id=store.store_id,
            product_id=product.product_id,
            baseline_daily_sales=10.0,
            promo_daily_sales=15.0,
            actual_lift=1.5,
        )
        test_db.add(existing_result)
        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["total_candidates"] == 1
        assert summary["promotions_evaluated"] == 0


@pytest.mark.xfail(
    reason=(
        "retail/promo_tracking.py uses Transaction.transaction_date which does not "
        "exist on the ORM model (the column is Transaction.timestamp). Additionally, "
        "PromotionResult is constructed with kwargs (baseline_daily_avg, promo_daily_avg, "
        "expected_lift, variance_pct, needs_review) that are absent from the ORM model "
        "(which has baseline_daily_sales, promo_daily_sales with no extra columns). "
        "These bugs must be fixed in the source before this test can pass."
    ),
    strict=True,
)
class TestFullEndToEndPath:
    async def test_measures_lift_and_writes_promotion_result_to_db(self, test_db):
        """
        Full path: promotion in window + transaction data → PromotionResult written.

        This test is expected to fail due to schema mismatches documented above.
        """
        from sqlalchemy import select

        from retail.promo_tracking import measure_promotion_effectiveness

        store, product = await _seed_base(test_db)
        end_date = TODAY - timedelta(days=10)
        start_date = end_date - timedelta(days=7)
        baseline_start = start_date - timedelta(days=30)

        promo = _make_promo(
            store.store_id,
            product.product_id,
            start_date=start_date,
            end_date=end_date,
            expected_lift=1.5,
        )
        test_db.add(promo)
        await test_db.flush()

        # Baseline transactions (30 days before promo)
        for i in range(30):
            txn_date = baseline_start + timedelta(days=i)
            txn = Transaction(
                customer_id=CUSTOMER_ID,
                store_id=store.store_id,
                product_id=product.product_id,
                timestamp=datetime.combine(txn_date, datetime.min.time()),
                quantity=10,
                unit_price=2.50,
                total_amount=25.0,
                transaction_type="sale",
            )
            test_db.add(txn)

        # Promo period transactions
        promo_days = (end_date - start_date).days + 1
        for i in range(promo_days):
            txn_date = start_date + timedelta(days=i)
            txn = Transaction(
                customer_id=CUSTOMER_ID,
                store_id=store.store_id,
                product_id=product.product_id,
                timestamp=datetime.combine(txn_date, datetime.min.time()),
                quantity=18,  # 1.8x lift
                unit_price=2.25,
                total_amount=40.5,
                transaction_type="sale",
            )
            test_db.add(txn)

        await test_db.flush()

        summary = await measure_promotion_effectiveness(test_db, CUSTOMER_ID, lookback_days=14)

        assert summary["promotions_evaluated"] == 1

        results = (
            (await test_db.execute(select(PromotionResult).where(PromotionResult.promotion_id == promo.promotion_id)))
            .scalars()
            .all()
        )
        assert len(results) == 1
        result = results[0]
        assert abs(result.actual_lift - 1.8) < 0.01
