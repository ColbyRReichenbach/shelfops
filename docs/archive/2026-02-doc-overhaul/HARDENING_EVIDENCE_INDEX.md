# ShelfOps Hardening Evidence Index

_Last updated: February 15, 2026_

This file records command outputs and test artifacts for hardening closure.

## Command Evidence

| command | result | notes |
|---|---|---|
| `cd backend && python3 -m pytest tests -q` | pass | `267 passed` |
| `cd backend && ruff check .` | pass | No lint violations |
| `cd backend && ruff format --check .` | pass | All files formatted |
| `cd frontend && npm run lint` | pass | ESLint clean |
| `cd frontend && npm run build` | pass | Production build completed (bundle-size warning only) |
| `PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py --contract contracts/demo_smb/smb_csv/v1.yaml --sample-path backend/tests/fixtures/contracts/sample_smb.csv` | pass | Contract validation passed with semantic DQ + cost confidence |
| `PYTHONPATH=backend python3 backend/scripts/validate_enterprise_seed.py --input data/seed_smoke --strict` | pass | All strict checks passed, including EDI `846/850/856/810` |
| `cd backend && PYTHONPATH=. python3 -c \"from workers.retrain import _next_version; print(_next_version())\"` | pass | Retrain smoke returned `v2` |

## Artifact Evidence

| artifact | status |
|---|---|
| `docs/HARDENING_TRACKER.md` | created |
| `docs/HARDENING_RUNBOOK.md` | created |
| `docs/HARDENING_BASELINE_2026_02_15.md` | created |
| `backend/tests/test_models_api.py` | added |
| `backend/tests/test_contract_mapper.py` | expanded |
| `data/seed_smoke/edi/EDI850_20260215_001.edi` | added |
| `data/seed_smoke/edi/EDI856_20260215_001.edi` | added |
| `data/seed_smoke/edi/EDI810_20260215_001.edi` | added |
