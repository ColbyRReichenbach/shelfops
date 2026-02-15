# Cross-Domain Readiness

_Last updated: February 15, 2026_

This document summarizes current readiness for multi-dataset model validation.

## Current Status

- Canonical data-contract layer is implemented: `backend/ml/data_contracts.py`
- Validation utility is implemented: `backend/scripts/validate_training_datasets.py`
- Latest validation report: `docs/DATASET_VALIDATION_REPORT.md`

## Dataset Readiness Snapshot

Based on the latest report:

1. Favorita: `ready` (daily, `EC`)
2. Synthetic seed transactions: `ready` (daily, `US`)
3. Walmart: `ready` (weekly, `US`)
4. Rossmann: `ready` (daily, `DE`)

## What "Cross-Domain Ready" Means

For forecasting claims beyond one domain, ShelfOps requires:

1. At least two public retail datasets in `ready` state.
2. Canonical contract validation passing for each dataset.
3. In-domain and cross-domain evaluation tables recorded in `docs/TUNING_PROTOCOL.md`.

## Next Actions

1. Keep canonical contract validation in CI via `contract-validation-suite`.
2. Re-run dataset readiness report whenever datasets change:

```bash
PYTHONPATH=backend python3 backend/scripts/validate_training_datasets.py --base-dir . --output docs/DATASET_VALIDATION_REPORT.md
```

3. Keep baseline and cross-domain evaluation tables current in `docs/TUNING_PROTOCOL.md`.
4. Maintain tenant contract profiles under `contracts/<tenant>/<source>/v1.yaml` for onboarding readiness.
