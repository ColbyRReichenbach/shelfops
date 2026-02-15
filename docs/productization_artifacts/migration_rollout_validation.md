# Migration Rollout Validation

- Executed at: 2026-02-15
- Environment: local Docker Timescale/Postgres (`timescale/timescaledb:latest-pg15`)
- Validation database: `shelfops_audit`

## Commands

```bash
PGPASSWORD=dev_password psql -h localhost -p 5432 -U shelfops -d postgres -c "DROP DATABASE IF EXISTS shelfops_audit;"
PGPASSWORD=dev_password psql -h localhost -p 5432 -U shelfops -d postgres -c "CREATE DATABASE shelfops_audit;"
cd backend && PYTHONPATH=. DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' alembic upgrade head
cd backend && PYTHONPATH=. DATABASE_URL='postgresql+asyncpg://shelfops:dev_password@localhost:5432/shelfops_audit' alembic current
```

## Result

- Upgrade path completed end-to-end from base migration to `007`.
- `alembic current` returned `007 (head)`.
- Readiness tables and dependent migrations are deployable on Postgres/Timescale.
