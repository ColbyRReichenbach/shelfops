# Model Performance Log

_Generated at: 2026-02-15T15:13:58.525353+00:00_

This file is auto-generated during model registration (`register_model`).

## Data Sources

- `backend/models/registry.json`
- `backend/models/champion.json`

## Decision Log

| order | version | model_name | dataset | tier | rows_trained | mae | mape | status | trained_at | promoted_at | decision | decision_basis |
|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---|
| 1 | v1 | demand_forecast | favorita | cold_start | 27 | 41.978588 | 0.285490 | champion | 2026-02-10T13:57:51.974315+00:00 | 2026-02-10T13:57:51.974341+00:00 | promoted_to_champion | status=champion and champion pointer matches |
| 2 | v2 | demand_forecast | tenant_db | cold_start | 3668 | 5.074499 | 1.132813 | candidate | 2026-02-15T15:09:34.777096+00:00 | None | candidate_pending | registered but not promoted yet |
| 3 | v3 | demand_forecast | tenant_db | cold_start | 3668 | 5.074499 | 1.132813 | candidate | 2026-02-15T15:11:16.500860+00:00 | None | candidate_pending | registered but not promoted yet |
| 4 | v4 | demand_forecast | tenant_db | cold_start | 3668 | 5.074499 | 1.132813 | candidate | 2026-02-15T15:13:58.524344+00:00 | None | candidate_pending | registered but not promoted yet |

## Notes

- This log is append-only through `registry.json` updates.
- Runtime champion/challenger truth in production comes from Postgres model tables.
