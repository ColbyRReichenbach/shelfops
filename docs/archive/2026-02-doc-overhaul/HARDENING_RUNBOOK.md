# ShelfOps Hardening Runbook

_Last updated: February 15, 2026_

This runbook is the fixed command set for scoped hardening verification.

## Backend

```bash
cd backend
python3 -m pytest tests -q
ruff check .
ruff format --check .
```

## Frontend

```bash
cd frontend
npm run lint
npm run build
```

## Contract and Integration Validation

```bash
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py \
  --contract contracts/demo_smb/smb_csv/v1.yaml \
  --sample-path backend/tests/fixtures/contracts/sample_smb.csv

PYTHONPATH=backend python3 backend/scripts/validate_enterprise_seed.py \
  --input data/seed_smoke \
  --strict
```

## Retrain / Backtest Smoke

```bash
cd backend
PYTHONPATH=. python3 - <<'PY'
from workers.retrain import _next_version
print("next_version", _next_version())
PY
```

Record resulting outputs in `docs/HARDENING_EVIDENCE_INDEX.md`.
