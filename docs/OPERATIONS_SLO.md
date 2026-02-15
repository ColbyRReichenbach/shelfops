# ShelfOps Operations SLOs

_Last updated: February 15, 2026_

## Purpose

Define runtime reliability targets for SMB launch-candidate operations.

## SLOs

| SLO ID | Metric | Target | Measurement Window | Breach Rule |
|---|---|---|---|---|
| SLO-001 | Forecast freshness | 99% of active tenants have forecast rows generated in last 24h | rolling 7 days | breach if <99% for 2 consecutive windows |
| SLO-002 | Accuracy freshness | 99% of active tenants have accuracy rows generated in last 24h | rolling 7 days | breach if <99% for 2 consecutive windows |
| SLO-003 | Integration sync health | 99% of connected integrations within source SLA (`24h` default, `48h` EDI) | rolling 7 days | breach if source-level `sla_status=breach` for >1 window |

## Source of Metrics

1. `DemandForecast` recency for SLO-001.
2. `ForecastAccuracy` recency for SLO-002.
3. `/api/v1/integrations/sync-health` and `integration_sync_log` for SLO-003.

## Alert Thresholds

1. `warning`: one-window miss below SLO target.
2. `critical`: two consecutive windows below SLO target.
3. `sev1`: zero fresh forecasts/accuracy for any production-tier tenant.

## Escalation

1. Follow `docs/INTEGRATION_INCIDENT_RUNBOOK.md` for sync and stale-feed incidents.
2. Block auto-promotion if SLO-001 or SLO-002 is in critical state.
3. Record incident summary + mitigation in release notes before re-enabling promotions.
