# ShelfOps SLO Policy

- Last verified date: February 15, 2026
- Audience: operations and platform engineering
- Scope: reliability targets for SMB launch-candidate operation
- Source of truth: runtime metrics paths and integration health endpoints

## SLOs

| SLO | Target | Status |
|---|---|---|
| Forecast freshness | 99% of active tenants within last 24h, rolling 7d | `implemented` |
| Accuracy freshness | 99% of active tenants within last 24h, rolling 7d | `implemented` |
| Integration SLA freshness | 99% within source SLA windows | `implemented` |

## Alerting Policy

- `warning`: one-window miss (`implemented`)
- `critical`: two-window miss (`implemented`)
- `sev1`: no fresh forecasts/accuracy for production-tier tenant (`implemented`)

## Operational Gate

Auto-promotion should be blocked when core SLOs are in critical state (`partial`, policy target; not yet enforced as an explicit SLO gate in promotion code paths).
