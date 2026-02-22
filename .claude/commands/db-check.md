Audit the database schema and migration state for ShelfOps.

Steps:
1. Read `backend/db/models.py` — enumerate all 27 expected tables
2. Read `backend/db/migrations/versions/` — list all migrations
3. Check that every tenant-scoped table has a `customer_id` column
4. Verify that `transactions` and `inventory_levels` are configured as hypertables
5. Identify any model fields without a corresponding migration

## Database Audit Report

**Migration State**: [count of migrations, latest version hash]

**Table Count**: [actual vs expected 27]

**Tenant Isolation**: [list any tables missing `customer_id`]

**Hypertables**: [confirm `transactions` and `inventory_levels`]

**Schema Drift**: [any model fields without migration coverage]

**Recommended Actions**: [specific fixes if any issues found]
