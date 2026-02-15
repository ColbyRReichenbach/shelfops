# Training Dataset Validation Report

| dataset | path | status | rows | stores | products | date_min | date_max | frequency | country | notes |
|---|---|---|---:|---:|---:|---|---|---|---|---|
| favorita | `data/kaggle/favorita` | `ready` | 3000888 | 54 | 33 | 2013-01-01 | 2017-08-15 | daily | EC | Canonical contract valid |
| walmart | `data/kaggle/walmart` | `ready` | 421570 | 45 | 81 | 2010-02-05 | 2012-10-26 | weekly | US | Canonical contract valid |
| rossmann | `data/kaggle/rossmann` | `ready` | 1017209 | 1115 | 1 | 2013-01-01 | 2015-07-31 | daily | DE | Canonical contract valid |
| seed_synthetic | `data/seed` | `ready` | 845838 | 15 | 500 | 2025-08-20 | 2026-02-15 | daily | US | Canonical contract valid |

## Interpretation

- `ready`: canonical contract loads and required fields are present.
- `missing`: dataset directory is not present locally.
- `error`: loader failed (usually missing expected source files).
- Public datasets are training/evaluation domains only and do not populate live tenant catalogs.
