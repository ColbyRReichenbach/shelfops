# ShelfOps Project Deep Dive

- Last verified date: March 9, 2026
- Status: retired as a canonical technical source

This file previously contained a long-form technical narrative that described an older
XGBoost/LSTM ensemble path, category-tier training flow, and outdated promotion gates.
Those details no longer match the active runtime.

Use these files instead:

- `docs/overview/technical_overview.md`
- `TECHNICAL.md`
- `docs/engineering/model_tuning_and_dataset_readiness.md`
- `docs/engineering/ml_effectiveness.md`
- `docs/demo/CLAIMS_LEDGER.md`

Reason for retirement:

- the live forecaster is now LightGBM-first
- promotion gates are business-first and fail closed
- segmented category training is not part of the active Favorita workflow
- demo and production claims are tracked separately in the claims ledger
