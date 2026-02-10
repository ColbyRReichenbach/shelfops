# Workflow: Setup Database

**Purpose**: Initialize PostgreSQL + TimescaleDB for ShelfOps

**Agent**: data-engineer

**Duration**: 2-3 hours

**Prerequisites**: 
- PostgreSQL 15 installed
- TimescaleDB extension available
- Alembic configured

---

## Steps

### 1. Install TimescaleDB Extension

```sql
-- Connect to postgres database
CREATE DATABASE shelfops;
\c shelfops;

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Verify
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';
```

### 2. Configure Alembic

```python
# alembic.ini
sqlalchemy.url = postgresql://user:pass@localhost/shelfops

# alembic/env.py
from db.models import Base

target_metadata = Base.metadata
```

### 3. Create Initial Migration

```bash
# Generate migration from models
alembic revision --autogenerate -m "initial_schema"

# Review migration file
# alembic/versions/001_initial_schema.py
```

### 4. Run Migration

```bash
# Apply migration
alembic upgrade head

# Verify tables created
psql -d shelfops -c "\dt"
```

### 5. Create TimescaleDB Hypertables

```sql
-- Convert transactions to hypertable
SELECT create_hypertable('transactions', 'timestamp');

-- Convert inventory_levels to hypertable
SELECT create_hypertable('inventory_levels', 'timestamp');

-- Add retention policy (keep 2 years)
SELECT add_retention_policy('transactions', INTERVAL '2 years');
SELECT add_retention_policy('inventory_levels', INTERVAL '2 years');
```

### 6. Create Indexes

```sql
-- Foreign key indexes
CREATE INDEX idx_transactions_store ON transactions(store_id);
CREATE INDEX idx_transactions_product ON transactions(product_id);
CREATE INDEX idx_transactions_customer ON transactions(customer_id);

-- Composite indexes
CREATE INDEX idx_transactions_store_time ON transactions(store_id, timestamp DESC);
CREATE INDEX idx_inventory_store_product_time ON inventory_levels(store_id, product_id, timestamp DESC);

-- Partial indexes
CREATE INDEX idx_alerts_open ON alerts(store_id, created_at DESC) WHERE status = 'open';
```

### 7. Seed Test Data (Development Only)

```python
# scripts/seed_test_data.py
import asyncio
from db.session import AsyncSessionLocal
from db.models import Customer, Store, Product
import uuid

async def seed_data():
    async with AsyncSessionLocal() as session:
        # Create test customer
        customer = Customer(
            customer_id=uuid.uuid4(),
            company_name="Test Retailer",
            subscription_tier="growth"
        )
        session.add(customer)
        
        # Create test store
        store = Store(
            store_id=uuid.uuid4(),
            customer_id=customer.customer_id,
            name="Test Store #001",
            city="Charlotte",
            state="NC"
        )
        session.add(store)
        
        # Create test products
        for i in range(100):
            product = Product(
                product_id=uuid.uuid4(),
                customer_id=customer.customer_id,
                sku=f"TEST-{i:04d}",
                name=f"Test Product {i}",
                category="grocery",
                retail_price=9.99
            )
            session.add(product)
        
        await session.commit()

if __name__ == "__main__":
    asyncio.run(seed_data())
```

### 8. Verify Setup

```sql
-- Check table counts
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check hypertables
SELECT hypertable_name, num_dimensions 
FROM timescaledb_information.hypertables;

-- Check indexes
SELECT tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public'
ORDER BY tablename;
```

---

## Checklist

- [ ] PostgreSQL 15 installed and running
- [ ] TimescaleDB extension created
- [ ] Alembic configured
- [ ] Initial migration created and applied
- [ ] All 15 tables created
- [ ] Hypertables created (transactions, inventory_levels)
- [ ] Indexes created (20+ indexes)
- [ ] Retention policies added
- [ ] Test data seeded (development only)
- [ ] Verification queries run successfully

---

## Troubleshooting

**Issue**: TimescaleDB extension not found  
**Fix**: Install TimescaleDB first: `apt install timescaledb-postgresql-15`

**Issue**: Migration fails  
**Fix**: Check alembic/versions/*.py for errors, run `alembic downgrade -1` then fix and retry

**Issue**: Slow queries  
**Fix**: Run `EXPLAIN ANALYZE <query>` to identify missing indexes

---

**Last Updated**: 2026-02-09
