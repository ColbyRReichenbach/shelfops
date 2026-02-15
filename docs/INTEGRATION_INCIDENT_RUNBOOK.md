# Integration Incident Runbook

_Last updated: February 15, 2026_

## Scope

Operational response for degraded integration health (EDI/SFTP/POS/event feeds).

## Trigger Conditions

- `GET /api/v1/integrations/sync-health` returns stale/failed status.
- Worker logs show repeated sync failures.
- Contract validator rejects inbound payloads at onboarding or runtime.

## Triage Steps

1. Confirm tenant and integration source impacted.
2. Check latest entries in `integration_sync_log` for `sync_status`, `error_message`, and `records_synced`.
3. Determine blast radius:
- single source
- single tenant
- multi-tenant
4. Classify severity:
- `sev1`: no ingest path for active tenant
- `sev2`: partial feed degradation
- `sev3`: delayed but recovering feed

## Immediate Actions

1. If malformed payload spike: isolate source and preserve raw payload for audit.
2. If schema drift: run `backend/scripts/validate_customer_contract.py` against latest sample.
3. If stale feed: validate scheduler dispatch and worker queue health.
4. If data gap affects model quality: block promotion and keep current champion routing.

## Recovery Validation

1. Re-run integration fixture tests for impacted source.
2. Confirm new sync logs show `success` with expected record counts.
3. Recompute forecast accuracy window if delayed data affected evaluation.
4. Record incident details and mitigations in release notes.

## Escalation

- Escalate to platform owner when:
  - repeated failures exceed SLA windows,
  - cross-tenant impact is observed,
  - source semantics become non-representable and require adapter work.
