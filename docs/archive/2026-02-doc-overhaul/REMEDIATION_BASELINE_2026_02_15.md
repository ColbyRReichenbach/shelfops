# Remediation Baseline - 2026-02-15

This baseline captures the pre-remediation audit state that started the 67/100 score.

## Audit Baseline

- Source scorecard: `docs/AUDIT_SCORECARD.md`
- Source findings: `docs/AUDIT_FINDINGS_REGISTER.md`
- Scope: F-001 through F-016

## Baseline Runtime Checks (from audit)

- `PYTHONPATH=backend python3 -m pytest backend/tests -q`
- `ruff check backend/ --config pyproject.toml`
- `ruff format --check backend/ --config pyproject.toml`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

## Rerun Command Set (Source of Truth)

```bash
# Backend quality gates
PYTHONPATH=backend python3 -m pytest backend/tests -q
ruff check backend/ --config pyproject.toml
ruff format --check backend/ --config pyproject.toml

# Frontend quality gates
cd frontend && npm run lint
cd frontend && npm run build

# Dataset benchmarks
PYTHONPATH=backend python3 backend/scripts/benchmark_datasets.py \
  --max-rows 200000 \
  --output-json backend/reports/dataset_benchmark_baseline.json

PYTHONPATH=backend python3 backend/scripts/benchmark_dataset_combos.py \
  --max-rows-each 120000 \
  --output-json backend/reports/dataset_combo_benchmark.json

# Contract and enterprise validation
PYTHONPATH=backend python3 backend/scripts/validate_customer_contract.py \
  --contract contracts/demo_smb/smb_csv/v1.yaml \
  --sample-path backend/tests/fixtures/contracts/sample_smb.csv

python3 backend/scripts/validate_enterprise_seed.py --input data/seed_ci --strict
```
