# ShelfOps Integration Incident Runbook

- Last verified date: February 15, 2026
- Audience: operations and integration engineering
- Scope: incident response for EDI/SFTP/event and sync-health degradations
- Source of truth: integration router contracts and worker behavior

## Trigger Conditions

- Sync-health endpoint indicates stale or breach status (`implemented`).
- Worker logs show repeated ingestion failures (`implemented`).
- Contract validation rejects runtime payloads (`implemented`).

## Response Workflow

1. Identify impacted tenant and source (`implemented`).
2. Inspect `integration_sync_log` evidence and failure payload (`implemented`).
3. Classify severity (`implemented`).
4. Run source-specific recovery checks (`implemented`).
5. Revalidate sync-health and logs before clearing incident (`implemented`).

## Escalation Boundaries

- Multi-tenant blast radius or repeated SLA breach: escalate immediately (`implemented`).
- Non-representable schema drift requiring adapter work: escalate to platform owner (`implemented`).
