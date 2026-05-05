# Benchmark Workspace Reset

Use this runbook when resetting a local or Neon-backed ShelfOps workspace to the
current pre-pilot benchmark state.

## Evidence Boundary

This reset creates a benchmark walkthrough, not a measured merchant pilot.

- M5/Walmart sales history is benchmark evidence.
- Inventory, supplier, reorder, and replenishment scaffolding around M5 is
  simulated/provisional operational context.
- FreshRetailNet-50K anomaly evidence is benchmark/shadow evidence.
- CSV and Square become measured evidence only after an authorized merchant data
  flow and observed outcome windows.

## Database URL

The Python runtime uses SQLAlchemy's asyncpg driver. For Neon, set
`DATABASE_URL` in this shape:

```bash
export DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST/DB?ssl=require"
```

Do not commit a real credential-bearing connection string. If Neon gives a
`postgresql://...?...sslmode=require&channel_binding=require` URL, convert it for
the ShelfOps Python runtime by changing the scheme to `postgresql+asyncpg://`
and using `?ssl=require`.

## Reset Commands

From the repo root:

```bash
APP_ENV=local DEBUG=true DATABASE_URL="$DATABASE_URL" \
  PYTHONPATH=backend python3 -m alembic -c backend/alembic.ini upgrade head

APP_ENV=local DEBUG=true DATABASE_URL="$DATABASE_URL" \
  PYTHONPATH=backend python3 backend/scripts/bootstrap_benchmark_workspace.py --wipe-existing

APP_ENV=local DEBUG=true DATABASE_URL="$DATABASE_URL" \
  PYTHONPATH=backend python3 backend/scripts/sync_benchmark_evidence_to_db.py
```

For a local Docker database, `./scripts/setup_production.sh` may be used before
the two benchmark scripts. For Neon, prefer the explicit `DATABASE_URL` path
above so the migration and bootstrap commands target the same database.

## Expected State

After the reset, the workspace should have:

- one `Production Pilot` tenant
- M5 benchmark products and positive-sales transaction history loaded into the
  operational tables
- products spanning `FOODS`, `HOBBIES`, and `HOUSEHOLD`
- forecast, forecast-accuracy, reorder-point, alert, replenishment, and
  recommendation-outcome rows
- benchmark dataset snapshots for M5/Walmart and FreshRetailNet-50K
- demand-forecast champion/challenger rows with benchmark provenance
- anomaly champion/challenger rows, benchmark anomaly runs, and anomaly shadow
  predictions sourced from FreshRetailNet-50K evidence
- a connected `csv` integration row representing the benchmark upload path

Experiment spec templates are served by the backend from
`backend/ml/experiment_specs.py`. Persisted `experiment_specs` rows are created
when Model Lab or the experiments API materializes a spec for a run, so an empty
`experiment_specs` table immediately after reset is valid.

## Readiness Probe

Use this probe when validating a reset:

```bash
APP_ENV=local DEBUG=true DATABASE_URL="$DATABASE_URL" PYTHONPATH=backend python3 - <<'PY'
import asyncio
from sqlalchemy import text
from db.session import AsyncSessionLocal

TABLES = [
    "customers", "stores", "products", "transactions", "inventory_levels",
    "demand_forecasts", "forecast_accuracy", "replenishment_recommendations",
    "recommendation_outcomes", "integrations", "dataset_snapshots",
    "model_versions", "model_experiments", "experiment_specs",
    "anomaly_detection_runs", "anomaly_shadow_predictions",
]

async def main():
    async with AsyncSessionLocal() as db:
        version = (await db.execute(text("select version_num from alembic_version"))).scalar_one()
        print(f"alembic_version={version}")
        for table in TABLES:
            count = (await db.execute(text(f"select count(*) from {table}"))).scalar_one()
            print(f"{table}={count}")

asyncio.run(main())
PY
```

The current Neon baseline validated on 2026-04-30 at Alembic revision `019` with
60 products, 16,092 operational transaction rows, 1,920 forecast rows, 24
replenishment recommendations, 24 recommendation outcomes, 4 model-version rows,
2 model-experiment rows, 2 anomaly runs, and 16 anomaly shadow predictions.
