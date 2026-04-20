#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! docker compose ps api >/dev/null 2>&1; then
  echo "Docker Compose API service is not available. Start the stack first with:"
  echo "  docker compose up -d db redis redpanda api"
  exit 1
fi

echo "=== ShelfOps Sample Merchant Bootstrap ==="
echo ""
echo "Loading the production pilot tenant with deterministic sample merchant data..."
docker compose exec -T api env PYTHONPATH=/app python scripts/bootstrap_sample_merchant.py "$@"
echo ""
echo "Next steps:"
echo "  1. Open the UI and confirm Data Readiness reflects the seeded production-tier walkthrough state."
echo "  2. Review Replenishment, Impact, Operations, and Model Performance."
echo "  3. Use this tenant as the canonical pre-pilot walkthrough until a real merchant is onboarded."
