# PostgreSQL + TimescaleDB Skill

**Purpose**: Design and optimize PostgreSQL databases for time-series retail data

**When to use**: Database schema design, migrations, query optimization, time-series operations

---

## Core Competencies

### 1. Time-Series Data Modeling (TimescaleDB)

**Best Practice**: Partition by time for retail transaction/inventory data

```sql
-- Create hypertable (automatically partitions by time)
CREATE TABLE transactions (
    transaction_id UUID PRIMARY KEY,
    store_id UUID NOT NULL,
    product_id UUID NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    quantity INT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL
);

-- Convert to hypertable (CRITICAL for time-series performance)
SELECT create_hypertable('transactions', 'timestamp');

-- Retention policy (keep only last 2 years)
SELECT add_retention_policy('transactions', INTERVAL '2 years');
```

**Why TimescaleDB**:
- 10-100x faster queries on time-range filters
- Automatic partitioning (no manual PARTITION BY needed)
- Compression (70-95% storage savings on old data)
- Continuous aggregates (pre-computed rollups)

**When to use hypertables**:
- ✅ Transactions (POS sales)
- ✅ Inventory levels (snapshots over time)
- ✅ Forecasts (predictions over time)
- ❌ Products (relatively static, no time dimension)
- ❌ Stores (metadata, updated rarely)

---

### 2. Multi-Tenant Schema Design

**Pattern**: Single database, row-level security

```sql
-- All tables have customer_id
CREATE TABLE products (
    product_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,  -- Tenant isolation
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    -- ... other columns
    UNIQUE(customer_id, sku)  -- SKUs unique per customer
);

-- Row-level security (RLS)
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

-- Policy: Users only see their customer's data
CREATE POLICY customer_isolation ON products
    USING (customer_id = current_setting('app.current_customer_id')::UUID);

-- In application, set customer context per request
SET LOCAL app.current_customer_id = '<customer_uuid>';
```

**Why this approach**:
- ✅ Single deployment (easier ops)
- ✅ Cross-customer analytics possible
- ✅ Easier to scale vertically
- ❌ More complex security (must get RLS right)

**Alternative**: Separate database per customer
- ✅ Perfect isolation
- ✅ Simpler security
- ❌ Harder to maintain (100s of databases)
- ❌ No cross-customer analytics

**Decision**: Use row-level security for MVP, consider database-per-tenant at scale

---

### 3. Indexing Strategy

**Rule of thumb**: Index foreign keys, time columns, and frequent WHERE clauses

```sql
-- Foreign key indexes (ALWAYS)
CREATE INDEX idx_transactions_store ON transactions(store_id);
CREATE INDEX idx_transactions_product ON transactions(product_id);
CREATE INDEX idx_transactions_customer ON transactions(customer_id);

-- Composite indexes (for common query patterns)
CREATE INDEX idx_transactions_store_time ON transactions(store_id, timestamp DESC);
CREATE INDEX idx_inventory_store_product_time ON inventory_levels(store_id, product_id, timestamp DESC);

-- Partial indexes (for filtered queries)
CREATE INDEX idx_alerts_open ON alerts(store_id, created_at DESC) 
    WHERE status = 'open';

-- GIN index (for JSONB columns)
CREATE INDEX idx_metadata_gin ON anomalies USING GIN(metadata);
```

**Index cost**:
- ✅ Faster SELECT queries (10-1000x)
- ❌ Slower INSERTs (5-10%)
- ❌ More disk space (20-30%)

**When to add indexes**:
1. After identifying slow queries (EXPLAIN ANALYZE)
2. Foreign keys (relationships)
3. Common WHERE/JOIN clauses
4. ORDER BY columns (with DESC if sorting descending)

**When NOT to index**:
- ❌ Columns with low cardinality (boolean, status with 2-3 values)
- ❌ Tables with <10K rows (full scan is fast enough)
- ❌ Columns rarely queried

---

### 4. Query Optimization

**Pattern**: Use EXPLAIN ANALYZE to find bottlenecks

```sql
-- Example slow query
EXPLAIN ANALYZE
SELECT 
    p.name,
    SUM(t.quantity) AS total_sold
FROM transactions t
JOIN products p ON t.product_id = p.product_id
WHERE t.timestamp >= NOW() - INTERVAL '30 days'
GROUP BY p.name
ORDER BY total_sold DESC
LIMIT 10;

-- Look for:
-- ❌ Seq Scan (full table scan) - needs index
-- ❌ Hash Join - might need better indexes
-- ✅ Index Scan - good!
-- ✅ Bitmap Index Scan - good for OR conditions
```

**Common optimizations**:

**1. Partition pruning** (TimescaleDB automatic):
```sql
-- Query with time filter - only scans relevant partitions
SELECT * FROM transactions 
WHERE timestamp >= '2026-02-01' AND timestamp < '2026-03-01';
-- TimescaleDB automatically skips other months
```

**2. Aggregation pushdown**:
```sql
-- BAD: Compute on application side
results = db.execute("SELECT * FROM transactions WHERE ...")
total = sum(r['quantity'] for r in results)

-- GOOD: Let database aggregate
total = db.execute(
    "SELECT SUM(quantity) FROM transactions WHERE ..."
).scalar()
```

**3. Limit early**:
```sql
-- BAD: Sort all rows, then limit
SELECT * FROM products ORDER BY created_at DESC LIMIT 10;

-- GOOD: Use index to get top 10 directly
CREATE INDEX idx_products_created_desc ON products(created_at DESC);
-- Now query uses index scan, only fetches 10 rows
```

**4. Continuous aggregates** (pre-computed rollups):
```sql
-- Create materialized view (refreshed automatically)
CREATE MATERIALIZED VIEW daily_sales
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', timestamp) AS day,
    store_id,
    product_id,
    SUM(quantity) AS quantity_sold,
    SUM(total_amount) AS revenue
FROM transactions
GROUP BY day, store_id, product_id;

-- Refresh policy (every hour)
SELECT add_continuous_aggregate_policy('daily_sales',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Now queries on daily_sales are instant (pre-computed)
SELECT day, SUM(revenue) FROM daily_sales 
WHERE day >= '2026-02-01'
GROUP BY day;
```

---

### 5. Data Integrity Constraints

**Use constraints to enforce business rules at database level**

```sql
CREATE TABLE inventory_levels (
    id BIGSERIAL PRIMARY KEY,
    store_id UUID REFERENCES stores(store_id),
    product_id UUID REFERENCES products(product_id),
    timestamp TIMESTAMP NOT NULL,
    quantity_on_hand INT NOT NULL,
    quantity_allocated INT DEFAULT 0,
    
    -- Constraints
    CHECK (quantity_on_hand >= 0),  -- Can't be negative
    CHECK (quantity_allocated >= 0),
    CHECK (quantity_allocated <= quantity_on_hand),  -- Can't allocate more than on-hand
    
    -- Computed column (auto-calculated, stored)
    quantity_available INT GENERATED ALWAYS AS 
        (quantity_on_hand - quantity_allocated) STORED
);

-- Unique constraints
CREATE UNIQUE INDEX idx_reorder_points_current ON reorder_points(store_id, product_id)
    WHERE effective_to IS NULL;  -- Only one "current" reorder point per store/product
```

**Why constraints matter**:
- ✅ Prevent bad data at source
- ✅ Self-documenting (schema shows business rules)
- ✅ Faster than application validation (database enforces)
- ❌ Harder to change later (migrations required)

---

### 6. Migration Best Practices

**Tool**: Alembic (Python) for version-controlled migrations

```python
# migrations/versions/001_create_stores_table.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'stores',
        sa.Column('store_id', sa.UUID(), primary_key=True),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now())
    )
    
    op.create_index('idx_stores_customer', 'stores', ['customer_id'])

def downgrade():
    op.drop_table('stores')
```

**Migration rules**:
1. **Always reversible** (implement `downgrade()`)
2. **Idempotent** (can run multiple times safely)
3. **Test on copy of production data** before deploying
4. **Small incremental changes** (not 50 tables in one migration)
5. **Add columns with defaults** (avoids table rewrite)

**Safe column addition** (no downtime):
```sql
-- Step 1: Add column (nullable, with default)
ALTER TABLE products ADD COLUMN shelf_life_days INT DEFAULT NULL;

-- Step 2: Backfill data (in batches, off-peak hours)
UPDATE products SET shelf_life_days = 7 WHERE category = 'produce';
UPDATE products SET shelf_life_days = 30 WHERE category = 'dairy';

-- Step 3: Add NOT NULL constraint (after backfill complete)
ALTER TABLE products ALTER COLUMN shelf_life_days SET NOT NULL;
```

**Unsafe changes** (require downtime or more care):
- Dropping columns (data loss)
- Changing column types (requires rewrite)
- Adding NOT NULL without default (fails on existing rows)

---

### 7. Connection Pooling

**Problem**: Opening new database connection is expensive (10-50ms)

**Solution**: Connection pool (reuse connections)

```python
# Using SQLAlchemy (Python)
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://user:pass@localhost/shelfops',
    poolclass=QueuePool,
    pool_size=10,  # Number of persistent connections
    max_overflow=20,  # Additional connections under load
    pool_pre_ping=True,  # Check connection health before use
    pool_recycle=3600  # Recycle connections every hour
)
```

**Pool sizing**:
- **pool_size**: 10-20 for web applications (per instance)
- **max_overflow**: 2x pool_size
- **Total connections**: pool_size + max_overflow = 30

**Database max_connections**:
```sql
-- Check current setting
SHOW max_connections;  -- Default: 100

-- Calculate: (num_app_instances × pool_size) + buffer
-- Example: 3 instances × 10 pool = 30 + 20 buffer = 50 connections
```

---

### 8. Monitoring Queries

**View active queries**:
```sql
-- See what's running now
SELECT 
    pid,
    now() - query_start AS duration,
    state,
    query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Kill long-running query
SELECT pg_terminate_backend(pid) WHERE pid = <pid>;
```

**Slow query log**:
```sql
-- Enable slow query logging (queries > 100ms)
ALTER SYSTEM SET log_min_duration_statement = 100;  -- milliseconds
SELECT pg_reload_conf();

-- Logs appear in PostgreSQL log file
```

**Index usage stats**:
```sql
-- Find unused indexes (never scanned)
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Consider dropping unused indexes (after confirming they're not seasonal)
```

---

## Common Patterns for ShelfOps

### Pattern 1: Latest Inventory Snapshot

```sql
-- Get most recent inventory level per store/product
SELECT DISTINCT ON (store_id, product_id)
    store_id,
    product_id,
    timestamp,
    quantity_on_hand
FROM inventory_levels
ORDER BY store_id, product_id, timestamp DESC;

-- Faster with lateral join (if querying specific stores)
SELECT 
    s.store_id,
    p.product_id,
    latest.timestamp,
    latest.quantity_on_hand
FROM stores s
CROSS JOIN products p
CROSS JOIN LATERAL (
    SELECT timestamp, quantity_on_hand
    FROM inventory_levels i
    WHERE i.store_id = s.store_id AND i.product_id = p.product_id
    ORDER BY timestamp DESC
    LIMIT 1
) latest;
```

### Pattern 2: Sales Velocity (Rolling Average)

```sql
-- 7-day rolling average sales per store/product
SELECT 
    store_id,
    product_id,
    time_bucket('1 day', timestamp) AS day,
    AVG(quantity) OVER (
        PARTITION BY store_id, product_id
        ORDER BY time_bucket('1 day', timestamp)
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS avg_7d_sales
FROM transactions
WHERE timestamp >= NOW() - INTERVAL '30 days';
```

### Pattern 3: Alert Deduplication

```sql
-- Don't create duplicate alerts for same store/product
INSERT INTO alerts (store_id, product_id, alert_type, message, ...)
VALUES (...)
ON CONFLICT (store_id, product_id, alert_type) 
    WHERE status = 'open'
DO UPDATE SET
    message = EXCLUDED.message,
    updated_at = NOW();

-- Requires unique index:
CREATE UNIQUE INDEX idx_alerts_dedup ON alerts(store_id, product_id, alert_type)
    WHERE status = 'open';
```

---

## Testing Database Code

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Create test database session"""
    # Use separate test database
    engine = create_engine('postgresql://localhost/shelfops_test')
    
    # Run migrations
    alembic.command.upgrade(alembic_cfg, "head")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Rollback after test
    session.rollback()
    session.close()

def test_inventory_constraint(db_session):
    """Test that negative inventory is rejected"""
    from models import InventoryLevel
    
    # This should fail
    with pytest.raises(IntegrityError):
        db_session.add(InventoryLevel(
            store_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            quantity_on_hand=-5  # Negative - constraint violation
        ))
        db_session.commit()
```

---

## DO / DON'T

### DO
- ✅ Use TimescaleDB hypertables for time-series data
- ✅ Index foreign keys
- ✅ Add constraints (CHECK, NOT NULL, UNIQUE)
- ✅ Use EXPLAIN ANALYZE for slow queries
- ✅ Create migrations for schema changes
- ✅ Use connection pooling
- ✅ Monitor query performance

### DON'T
- ❌ Use SELECT * (specify columns)
- ❌ N+1 queries (use JOINs or eager loading)
- ❌ Store sensitive data unencrypted
- ❌ Skip migrations (manual ALTER TABLE)
- ❌ Over-index (every column doesn't need an index)
- ❌ Ignore slow query logs
- ❌ Run migrations in production without testing on copy first

---

## Resources

- TimescaleDB docs: https://docs.timescale.com/
- PostgreSQL performance tips: https://wiki.postgresql.org/wiki/Performance_Optimization
- Alembic (migrations): https://alembic.sqlalchemy.org/
- SQLAlchemy (ORM): https://www.sqlalchemy.org/

---

**Last Updated**: 2026-02-09  
**Version**: 1.0.0
