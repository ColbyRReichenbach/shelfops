#!/usr/bin/env bash
# Setup production environment: run migrations, ensure clean production tenant.
# No demo or synthetic data will be present.
#
# Usage: ./scripts/setup_production.sh
set -euo pipefail

cd "$(dirname "$0")/.."

use_compose_api=false
if docker compose ps --status running api >/dev/null 2>&1; then
  use_compose_api=true
fi

echo "=== ShelfOps Production Setup ==="
echo ""

echo "[1/3] Running database migrations..."
if [ "$use_compose_api" = true ]; then
  docker compose exec -T api env PYTHONPATH=/app alembic upgrade head
else
  cd backend && PYTHONPATH=. alembic upgrade head
  cd ..
fi

echo ""
echo "[2/3] Ensuring clean production tenant..."
python_cmd=$(cat <<'PY'
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from core.config import get_settings
from scripts.production_tenant import ensure_production_tenant

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        result = await ensure_production_tenant(db, wipe_synthetic=True)
        await db.commit()
    await engine.dispose()
    print("Production tenant ready:", result["name"])

asyncio.run(main())
PY
)

if [ "$use_compose_api" = true ]; then
  docker compose exec -T api env PYTHONPATH=/app python -c "$python_cmd"
else
  PYTHONPATH=backend python3 -c "$python_cmd"
fi

echo ""
echo "[3/3] Production ready."
echo ""
echo "  No data populated. Connect a POS system to begin receiving transaction data."
echo "  For a local walkthrough: ./scripts/bootstrap_sample_merchant.sh"
echo "  Start the API:     PYTHONPATH=backend uvicorn api.main:app --reload --port 8001"
echo "  Start the UI:      cd frontend && npm run dev"
echo "  Dashboard:         http://localhost:3000/"
