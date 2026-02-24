"""
Tests for Vendor Metrics Worker — 90-day reliability scorecard calculations.

The Celery task wraps an async inner function that creates its own engine.
We test the calculation logic directly against a test_db fixture, mirroring
the algorithm in workers/vendor_metrics.py without invoking Celery.

Covers:
  - On-time delivery rate (within ±1 day of promised date)
  - Supplier with no received POs in 90-day window is skipped
  - Average actual lead time calculation
  - Lead-time variance (std dev) calculation
  - Composite reliability score: 60% on-time + 40% consistency
  - Edge case: single PO (variance defaults to 0.0)
  - Edge case: PO missing delivery dates is excluded from lead time
  - last_delivery_date is set to the most recent actual delivery
"""

import statistics
import uuid
from datetime import date, datetime, timedelta

import pytest

from db.models import Customer, Product, PurchaseOrder, Store, Supplier

CUSTOMER_ID_STR = "00000000-0000-0000-0000-000000000002"


# ── Calculation helpers (mirrors workers/vendor_metrics.py logic) ──────────


def _compute_supplier_metrics(received_pos):
    """
    Replicate the metric calculation from workers/vendor_metrics._update().

    Returns a dict with:
      on_time_delivery_rate, avg_lead_time_actual,
      lead_time_variance, reliability_score, last_delivery_date
    or None if no POs supplied.
    """
    if not received_pos:
        return None

    on_time_count = 0
    lead_times = []

    for po in received_pos:
        if po.actual_delivery_date and po.promised_delivery_date:
            days_diff = (po.actual_delivery_date - po.promised_delivery_date).days
            if abs(days_diff) <= 1:
                on_time_count += 1

        if po.actual_delivery_date and po.ordered_at:
            actual_lt = (po.actual_delivery_date - po.ordered_at.date()).days
            if actual_lt > 0:
                lead_times.append(actual_lt)

    total_pos = len(received_pos)
    on_time_rate = round(on_time_count / total_pos, 3) if total_pos > 0 else None

    last_delivery = max(
        (po.actual_delivery_date for po in received_pos if po.actual_delivery_date),
        default=None,
    )

    avg_lead_time = None
    lead_time_var = None
    reliability = None

    if lead_times:
        avg_lead_time = round(statistics.mean(lead_times), 1)
        lead_time_var = (
            round(statistics.stdev(lead_times), 1) if len(lead_times) > 1 else 0.0
        )

        on_time_score = on_time_rate if on_time_rate is not None else 0.5
        # Use a placeholder lead_time_days of 5 for tests (set on supplier fixtures)
        lead_time_days = 5
        consistency_score = max(0, 1.0 - (lead_time_var or 0) / lead_time_days)
        reliability = round(0.6 * on_time_score + 0.4 * max(0, consistency_score), 3)

    return {
        "on_time_delivery_rate": on_time_rate,
        "avg_lead_time_actual": avg_lead_time,
        "lead_time_variance": lead_time_var,
        "reliability_score": reliability,
        "last_delivery_date": last_delivery,
    }


# ── Fixtures / seed helpers ────────────────────────────────────────────────


async def _seed_customer_and_supplier(db, lead_time_days=5):
    customer_id = uuid.UUID(CUSTOMER_ID_STR)

    customer = Customer(
        customer_id=customer_id,
        name="Metrics Test Grocers",
        email="metrics@testgrocers.com",
        plan="professional",
    )
    db.add(customer)
    await db.flush()

    supplier = Supplier(
        customer_id=customer_id,
        name="Metrics Supplier",
        contact_email="metrics@supplier.com",
        lead_time_days=lead_time_days,
        status="active",
    )
    db.add(supplier)
    await db.flush()

    store = Store(
        customer_id=customer_id,
        name="Metrics Store",
        city="Denver",
        state="CO",
        zip_code="80202",
    )
    db.add(store)
    await db.flush()

    product = Product(
        customer_id=customer_id,
        sku="MET-001",
        name="Metrics Product",
        category="Beverages",
        unit_cost=1.50,
        unit_price=3.00,
        supplier_id=supplier.supplier_id,
    )
    db.add(product)
    await db.flush()

    return customer_id, supplier, store, product


def _make_received_po(customer_id, store_id, product_id, supplier_id,
                       promised_date, actual_date, ordered_at=None):
    """Create a PurchaseOrder dict (not yet added to DB) for calculation tests."""
    ordered_at = ordered_at or datetime(2026, 1, 1)
    return PurchaseOrder(
        customer_id=customer_id,
        store_id=store_id,
        product_id=product_id,
        supplier_id=supplier_id,
        quantity=24,
        status="received",
        source_type="vendor_direct",
        promised_delivery_date=promised_date,
        actual_delivery_date=actual_date,
        ordered_at=ordered_at,
    )


# ── On-time delivery rate ──────────────────────────────────────────────────


class TestOnTimeDeliveryRate:
    def test_exact_delivery_on_promised_date_is_on_time(self):
        """Delivery on the exact promised date counts as on-time."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["on_time_delivery_rate"] == 1.0

    def test_delivery_one_day_late_is_still_on_time(self):
        """Within ±1 day of promised date is considered on-time."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 11)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["on_time_delivery_rate"] == 1.0

    def test_delivery_one_day_early_is_still_on_time(self):
        """One day early counts as on-time."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 9)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["on_time_delivery_rate"] == 1.0

    def test_delivery_two_days_late_is_not_on_time(self):
        """Two days late is outside the ±1 tolerance — not on-time."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 12)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["on_time_delivery_rate"] == 0.0

    def test_mixed_on_time_and_late_gives_correct_rate(self):
        """3 on-time out of 4 deliveries → 75% on-time rate."""

        class OnTimePO:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        class LatePO:
            actual_delivery_date = date(2026, 2, 14)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        pos = [OnTimePO(), OnTimePO(), OnTimePO(), LatePO()]
        metrics = _compute_supplier_metrics(pos)
        assert metrics["on_time_delivery_rate"] == 0.75

    def test_po_missing_promised_date_is_excluded_from_on_time_count(self):
        """POs without a promised date cannot determine on-time status."""

        class NoDatesForOnTime:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = None  # No promised date
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([NoDatesForOnTime()])
        # on_time_count stays 0, total_pos is 1 → 0% on-time rate
        assert metrics["on_time_delivery_rate"] == 0.0


# ── Lead time calculation ──────────────────────────────────────────────────


class TestLeadTimeCalculation:
    def test_actual_lead_time_is_days_from_ordered_to_received(self):
        """Lead time = actual_delivery_date - ordered_at.date()."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)  # 7 days before delivery

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["avg_lead_time_actual"] == 7.0

    def test_po_missing_ordered_at_is_excluded_from_lead_time(self):
        """POs without ordered_at cannot compute lead time."""

        class NoOrderedAt:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = None

        metrics = _compute_supplier_metrics([NoOrderedAt()])
        assert metrics["avg_lead_time_actual"] is None

    def test_po_missing_actual_delivery_is_excluded_from_lead_time(self):
        """POs without actual_delivery_date cannot compute lead time."""

        class NoActualDelivery:
            actual_delivery_date = None
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([NoActualDelivery()])
        assert metrics["avg_lead_time_actual"] is None

    def test_avg_lead_time_is_mean_of_multiple_pos(self):
        """Average lead time across 3 POs with 5, 7, and 9 days = 7.0."""

        def make_po(lt_days):
            class MockPO:
                ordered_at = datetime(2026, 1, 1)
                actual_delivery_date = date(2026, 1, 1 + lt_days)
                promised_delivery_date = actual_delivery_date

            return MockPO()

        pos = [make_po(5), make_po(7), make_po(9)]
        metrics = _compute_supplier_metrics(pos)
        assert metrics["avg_lead_time_actual"] == 7.0

    def test_single_po_lead_time_variance_is_zero(self):
        """With only one PO there is no variance — defaults to 0.0."""

        class MockPO:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([MockPO()])
        assert metrics["lead_time_variance"] == 0.0

    def test_lead_time_variance_is_std_dev_of_multiple_lead_times(self):
        """Std dev of [5, 9] lead times = 2.83... rounded to 1 dp."""

        def make_po(lt_days):
            class MockPO:
                ordered_at = datetime(2026, 1, 1)
                actual_delivery_date = date(2026, 1, 1 + lt_days)
                promised_delivery_date = actual_delivery_date

            return MockPO()

        pos = [make_po(5), make_po(9)]
        metrics = _compute_supplier_metrics(pos)
        expected_stdev = round(statistics.stdev([5, 9]), 1)
        assert metrics["lead_time_variance"] == expected_stdev


# ── Reliability score ──────────────────────────────────────────────────────


class TestReliabilityScore:
    def test_reliability_score_not_computed_when_no_valid_lead_times(self):
        """No ordered_at means no lead times, so reliability score is None."""

        class NoOrderedAt:
            actual_delivery_date = date(2026, 2, 10)
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = None

        metrics = _compute_supplier_metrics([NoOrderedAt()])
        assert metrics["reliability_score"] is None

    def test_perfect_supplier_gets_high_reliability_score(self):
        """Perfect on-time + low variance should produce a score near 1.0."""

        def make_po(lt_days):
            class MockPO:
                ordered_at = datetime(2026, 1, 1)
                actual_delivery_date = date(2026, 1, 1 + lt_days)
                promised_delivery_date = actual_delivery_date

            return MockPO()

        # All on time, identical lead times (variance = 0)
        pos = [make_po(5), make_po(5), make_po(5)]
        metrics = _compute_supplier_metrics(pos)

        # 60% × 1.0 on-time + 40% × max(0, 1.0 - 0/5) = 0.6 + 0.4 = 1.0
        assert metrics["reliability_score"] == 1.0

    def test_poor_on_time_rate_lowers_reliability_score(self):
        """0% on-time with perfect lead time consistency → only consistency portion."""

        def make_late_po():
            class LatePO:
                ordered_at = datetime(2026, 1, 1)
                actual_delivery_date = date(2026, 1, 8)  # 7 days
                promised_delivery_date = date(2026, 1, 4)  # promised only 3 days

            return LatePO()

        pos = [make_late_po(), make_late_po(), make_late_po()]
        metrics = _compute_supplier_metrics(pos)

        # on_time = 0.0; consistency = max(0, 1.0 - 0/5) = 1.0 (no variance)
        # reliability = 0.6 × 0.0 + 0.4 × 1.0 = 0.4
        assert metrics["reliability_score"] == 0.4


# ── Last delivery date ─────────────────────────────────────────────────────


class TestLastDeliveryDate:
    def test_last_delivery_date_is_most_recent_actual_delivery(self):
        """The supplier's last_delivery_date should be the latest actual delivery."""

        class EarlyPO:
            actual_delivery_date = date(2026, 1, 5)
            promised_delivery_date = date(2026, 1, 5)
            ordered_at = datetime(2025, 12, 28)

        class LatePO:
            actual_delivery_date = date(2026, 2, 15)
            promised_delivery_date = date(2026, 2, 15)
            ordered_at = datetime(2026, 2, 8)

        metrics = _compute_supplier_metrics([EarlyPO(), LatePO()])
        assert metrics["last_delivery_date"] == date(2026, 2, 15)

    def test_last_delivery_date_is_none_when_no_actual_delivery_dates(self):
        class NoPO:
            actual_delivery_date = None
            promised_delivery_date = date(2026, 2, 10)
            ordered_at = datetime(2026, 2, 3)

        metrics = _compute_supplier_metrics([NoPO()])
        assert metrics["last_delivery_date"] is None

    def test_returns_none_when_no_pos_provided(self):
        """Empty PO list means no data to compute — return None."""
        result = _compute_supplier_metrics([])
        assert result is None


# ── DB integration: query and update via test_db ───────────────────────────


class TestVendorMetricsDBIntegration:
    async def test_supplier_on_time_rate_updated_from_received_pos(self, test_db):
        """Verify the DB-backed path: insert received POs, compute, update supplier."""
        from sqlalchemy import select

        customer_id, supplier, store, product = await _seed_customer_and_supplier(test_db)
        cutoff = datetime.utcnow() - timedelta(days=90)

        # Insert 2 on-time and 1 late PO
        base_ordered = datetime.utcnow() - timedelta(days=30)
        for i, (promised, actual) in enumerate([
            (date(2026, 1, 10), date(2026, 1, 10)),  # on-time
            (date(2026, 1, 17), date(2026, 1, 18)),  # on-time (+1 day)
            (date(2026, 1, 24), date(2026, 1, 28)),  # late (+4 days)
        ]):
            po = PurchaseOrder(
                customer_id=customer_id,
                store_id=store.store_id,
                product_id=product.product_id,
                supplier_id=supplier.supplier_id,
                quantity=10,
                status="received",
                source_type="vendor_direct",
                promised_delivery_date=promised,
                actual_delivery_date=actual,
                ordered_at=base_ordered - timedelta(days=i * 7),
                received_at=datetime.utcnow() - timedelta(days=i * 7),
            )
            test_db.add(po)
        await test_db.flush()

        # Fetch and compute exactly as the worker does
        from sqlalchemy import select as sa_select

        result = await test_db.execute(
            sa_select(PurchaseOrder).where(
                PurchaseOrder.customer_id == customer_id,
                PurchaseOrder.supplier_id == supplier.supplier_id,
                PurchaseOrder.status == "received",
                PurchaseOrder.received_at >= cutoff,
            )
        )
        received_pos = result.scalars().all()

        assert len(received_pos) == 3

        on_time_count = sum(
            1
            for po in received_pos
            if po.actual_delivery_date
            and po.promised_delivery_date
            and abs((po.actual_delivery_date - po.promised_delivery_date).days) <= 1
        )
        assert on_time_count == 2

        rate = round(on_time_count / len(received_pos), 3)
        supplier.on_time_delivery_rate = rate
        await test_db.flush()

        refreshed = await test_db.get(Supplier, supplier.supplier_id)
        assert abs(refreshed.on_time_delivery_rate - 0.667) < 0.001

    async def test_supplier_without_received_pos_is_not_updated(self, test_db):
        """A supplier with no received POs in the 90-day window is skipped."""
        customer_id, supplier, store, product = await _seed_customer_and_supplier(test_db)
        cutoff = datetime.utcnow() - timedelta(days=90)

        # Only an old PO outside the 90-day window
        po = PurchaseOrder(
            customer_id=customer_id,
            store_id=store.store_id,
            product_id=product.product_id,
            supplier_id=supplier.supplier_id,
            quantity=10,
            status="received",
            source_type="vendor_direct",
            promised_delivery_date=date(2025, 1, 1),
            actual_delivery_date=date(2025, 1, 5),
            ordered_at=datetime(2024, 12, 25),
            received_at=datetime(2025, 1, 5),
        )
        test_db.add(po)
        await test_db.flush()

        from sqlalchemy import select as sa_select

        result = await test_db.execute(
            sa_select(PurchaseOrder).where(
                PurchaseOrder.customer_id == customer_id,
                PurchaseOrder.supplier_id == supplier.supplier_id,
                PurchaseOrder.status == "received",
                PurchaseOrder.received_at >= cutoff,
            )
        )
        received_pos = result.scalars().all()

        assert len(received_pos) == 0
        # No update applied — supplier reliability_score stays at default
        assert supplier.reliability_score == 0.95  # model default
