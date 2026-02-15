# ShelfOps API Contracts

- Last verified date: February 15, 2026
- Audience: frontend engineers, backend engineers, integrators
- Scope: canonical API shapes and deprecation policy
- Source of truth: router definitions under `backend/api/v1/routers/`

## Canonical Namespace

- Canonical namespace: `/api/v1/*` (`implemented`)
- Legacy aliases (`/ml/*`, `/models/*`, `/anomalies/*`) are compatibility paths with deprecation headers (`implemented`)
- Alias retirement date target: June 30, 2026 (`partial` operational timeline)

## Contracted Endpoints

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/v1/ml/backtests` | `implemented` | Backtest series for model monitoring. |
| `GET /api/v1/ml/health` | `implemented` | Aggregated ML health summary. |
| `GET /api/v1/ml/effectiveness` | `implemented` | Rolling effectiveness metrics and confidence band. |
| `GET /api/v1/ml/models/health` | `implemented` | Champion/challenger and retrain trigger surface. |
| `GET /api/v1/ml/models/history` | `implemented` | Model version history from DB-backed lifecycle table. |
| `POST /api/v1/ml/models/{version}/promote` | `implemented` | Admin-only manual promotion with registry/champion artifact sync. |
| `GET /api/v1/integrations/sync-health` | `implemented` | Integration freshness and SLA envelope. |

## Deprecation Headers (Alias Paths)

- `Deprecation: true`
- `Sunset: Wed, 30 Jun 2026 00:00:00 GMT`
- `X-API-Deprecated: Use /api/v1/ml/* endpoints`
- `Link: <canonical-path>; rel="successor-version"`

## Response Contract Notes

- Numeric values in examples are illustrative and shape-oriented (`implemented` policy).
- Unsupported or legacy fields are not part of canonical response contracts (`implemented` policy).
