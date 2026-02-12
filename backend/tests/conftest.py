"""
Test Configuration — Fixtures for async DB, test client, and mock data.

Uses per-test transactions with SAVEPOINT/rollback so each test gets a
clean database state while sharing the same session-level schema.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.deps import get_current_user, get_db, get_tenant_db
from api.main import app
from db.session import Base

# Use in-memory SQLite for tests (no TimescaleDB features).
# Shared cache so session-scoped engine and function-scoped sessions
# can share the same in-memory database.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

CUSTOMER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine and build all tables once."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine):
    """Create a test session wrapped in a transaction that rolls back after each test."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Use SAVEPOINT so nested commits inside app code don't end our transaction
        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(db_session, transaction):
            if transaction.nested and not transaction._parent.nested:
                session.sync_session.begin_nested()

        await conn.begin_nested()  # SAVEPOINT

        yield session

        await session.close()
        await trans.rollback()


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "sub": "auth0|test-user-id",
        "email": "test@shelfops.com",
        "customer_id": CUSTOMER_ID,
    }


@pytest.fixture
async def client(test_db, mock_user):
    """Create an async test client with dependency overrides."""

    async def override_get_db():
        yield test_db

    def override_get_current_user():
        return mock_user

    async def override_get_tenant_db():
        """Skip set_config (SQLite doesn't support it), return session directly."""
        return test_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_db(test_db):
    """Seed the test DB with basic entities for integration tests."""
    from db.models import Customer, Product, PurchaseOrder, Store, Supplier

    customer_id = uuid.UUID(CUSTOMER_ID)

    customer = Customer(
        customer_id=customer_id,
        name="Test Grocers",
        email="test@grocers.com",
        plan="professional",
    )
    test_db.add(customer)
    await test_db.flush()

    supplier = Supplier(
        customer_id=customer_id,
        name="Test Distributor",
        contact_email="orders@testdist.com",
        lead_time_days=5,
    )
    test_db.add(supplier)
    await test_db.flush()

    store = Store(
        customer_id=customer_id,
        name="Downtown Store",
        city="Minneapolis",
        state="MN",
        zip_code="55401",
    )
    test_db.add(store)
    await test_db.flush()

    product = Product(
        customer_id=customer_id,
        sku="SKU-0001",
        name="Test Product",
        category="Dairy",
        unit_cost=3.50,
        unit_price=5.99,
        supplier_id=supplier.supplier_id,
    )
    test_db.add(product)
    await test_db.flush()

    po = PurchaseOrder(
        customer_id=customer_id,
        store_id=store.store_id,
        product_id=product.product_id,
        supplier_id=supplier.supplier_id,
        quantity=48,
        status="suggested",
        source_type="vendor_direct",
        promised_delivery_date=date.today() + timedelta(days=5),
    )
    test_db.add(po)
    await test_db.flush()

    await test_db.commit()

    return {
        "customer_id": customer_id,
        "supplier": supplier,
        "store": store,
        "product": product,
        "po": po,
    }
