# ShelfOps — Observability: AI-Assisted Error Tracking & Log Intelligence

- Author: Engineering, February 24, 2026
- Status: **Spec — approved for implementation**
- Priority: P0 — prerequisite before first customer onboarding
- Prerequisite reading: `backend/api/main.py`, `backend/workers/celery_app.py`, `backend/core/config.py`

---

## Problem

One-person team. When something breaks with a real tenant's data, debugging speed depends entirely
on observability quality. Without it, "fix fast" becomes "grep logs in the dark." Standard error
tracking (Sentry-style) surfaces *what* broke but not *why* or *what to do about it*. For a solo
operator, the difference between a 10-minute fix and a 2-hour debug session is context — and
context assembly is exactly what an LLM is good at.

Two distinct problems:

1. **Errors**: unhandled exceptions in the API or workers need to surface with enough context
   to fix them quickly, in plain language, with a proposed resolution.
2. **Log anomalies**: slow degradation, tenant-specific weirdness, and ML distribution shifts
   don't throw exceptions — they show up as patterns in logs that no one is watching.

---

## Proposed Solution

Four layers, all building on infrastructure that already exists:

1. **Structured logging** — configure `structlog` (already imported, not yet configured) to
   emit consistent JSON with tenant context on every request and Celery task.
2. **Error capture middleware** — FastAPI exception handler that writes to a `error_events`
   TimescaleDB hypertable and queues an async LLM diagnosis task.
3. **LLM error diagnosis** — Celery task that feeds stack trace + context to Claude, gets back
   plain-English explanation + severity + proposed fix, delivers to Slack.
4. **Log anomaly detection** — Celery beat job every 15 minutes: statistical anomaly detection
   on log event patterns, LLM contextualization of anything unusual, Slack alert if actionable.

No external error tracking SaaS needed. Everything stored in the existing DB.

---

## Database Changes

### New Tables

```sql
-- error_events: one row per unhandled exception, with LLM diagnosis appended async
CREATE TABLE error_events (
    id              UUID            DEFAULT gen_random_uuid(),
    captured_at     TIMESTAMPTZ     NOT NULL,
    tenant_id       UUID,
    error_type      TEXT            NOT NULL,   -- exception class name
    error_message   TEXT            NOT NULL,
    stack_trace     TEXT            NOT NULL,
    request_path    TEXT,
    request_method  TEXT,
    celery_task     TEXT,                       -- populated for worker errors
    fingerprint     TEXT            NOT NULL,   -- sha256(error_type + last 3 stack frames)
    diagnosis       TEXT,                       -- LLM output, NULL until processed
    diagnosis_model TEXT,
    severity        TEXT            DEFAULT 'error',   -- 'warning'|'error'|'critical'
    resolved_at     TIMESTAMPTZ,
    PRIMARY KEY (id, captured_at)
);
SELECT create_hypertable('error_events', 'captured_at');
CREATE INDEX ON error_events (fingerprint, captured_at DESC);
CREATE INDEX ON error_events (tenant_id, captured_at DESC);

-- log_events: structured log sink for API requests and Celery tasks
CREATE TABLE log_events (
    id          UUID            DEFAULT gen_random_uuid(),
    logged_at   TIMESTAMPTZ     NOT NULL,
    level       TEXT            NOT NULL,       -- 'debug'|'info'|'warning'|'error'
    tenant_id   UUID,
    service     TEXT            NOT NULL,       -- 'api'|'worker'|'ml'
    operation   TEXT            NOT NULL,       -- endpoint path or task name
    duration_ms FLOAT,
    request_id  TEXT,
    metadata    JSONB           DEFAULT '{}',
    PRIMARY KEY (id, logged_at)
);
SELECT create_hypertable('log_events', 'logged_at');
CREATE INDEX ON log_events (service, operation, logged_at DESC);
CREATE INDEX ON log_events (tenant_id, logged_at DESC);

-- anomaly_events: detected log pattern anomalies with LLM context
CREATE TABLE anomaly_events (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    detected_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anomaly_type            TEXT        NOT NULL,   -- 'error_spike'|'latency'|'tenant_behavior'|'ml_drift'
    severity                TEXT        NOT NULL,   -- 'low'|'medium'|'high'|'critical'
    affected_tenant_id      UUID,
    affected_operation      TEXT,
    anomaly_score           FLOAT,                 -- z-score or isolation forest score
    context_summary         TEXT        NOT NULL,  -- LLM-generated plain English
    suggested_investigation TEXT,                  -- LLM-generated next steps
    raw_metrics             JSONB       DEFAULT '{}',
    resolved_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
```

**Alembic migration filename**: `add_observability_tables`

Note: TimescaleDB indexes on `error_events` and `log_events` hypertables are excluded from
Alembic autogenerate per project convention (`docs/MLOPS_STANDARDS.md`).

---

## API Changes

No new public endpoints. One internal-only endpoint for health/observability status:

```
GET /internal/observability/health
Auth: internal service token only (not tenant-auth)
Response: {
    "error_events_last_hour": int,
    "open_anomalies": int,
    "last_anomaly_check": ISO8601 | null,
    "log_pipeline_healthy": bool
}
```

This is used by the anomaly detection job to self-report and by future dashboards.

---

## ML / Business Logic Changes

### New Celery Task: `workers.observability.diagnose_error`

Triggered by: error capture middleware (immediate queue after exception is written to DB)

```
Input:
  error_event_id: UUID

Steps:
  1. Load error_event from DB (stack trace, context, tenant_id)
  2. Query last 5 similar fingerprint matches (has this happened before?)
  3. Read source file snippets for the top 3 stack frames (git-aware file read)
  4. If tenant_id present: load tenant state snapshot (sku_count, last_sync_at,
     model_version, last_retrain_at)
  5. Call Claude API (claude-haiku-4-5, structured output):
     - System prompt: ShelfOps codebase context, stack conventions, known patterns
     - User prompt: stack trace + source snippets + tenant state + error history
     - Response schema: {
         plain_english: str,        -- "The forecast job failed because..."
         likely_cause: str,         -- "SKU X has no sales data in the training window"
         severity: 'low'|'medium'|'high'|'critical',
         fix_type: 'config'|'env'|'data'|'code'|'unknown',
         proposed_fix: str,         -- specific actionable text
         is_recurring: bool
       }
  6. Update error_event.diagnosis with formatted output
  7. POST to Slack webhook with:
     - Severity emoji + plain_english (one line)
     - likely_cause
     - proposed_fix (inline code block if fix_type == 'code')
     - Link to error_event in DB (for full stack trace)
     - "Recurring (N times in 24h)" badge if is_recurring

Dedup: if same fingerprint was diagnosed in last 30 minutes, skip LLM call,
just increment count and update Slack thread.
```

### New Celery Beat Job: `workers.observability.detect_log_anomalies`

Schedule: every 15 minutes (offset from existing sync jobs)

```
Steps:
  1. Query log_events for last 15-minute window (current) and same window
     averaged over last 7 days (baseline).
  2. Compute per-operation metrics:
     - error_rate = errors / total requests
     - p95_latency_ms
     - unique_tenants_with_errors
  3. Z-score each metric vs. baseline. Flag if |z| > 2.5.
  4. Also run IsolationForest on the multivariate vector
     (error_rate, p95_latency, unique_tenants_erroring) — flags structural
     anomalies that individual z-scores miss.
  5. For any flagged operation:
     a. Sample 20 recent log_events around the anomaly window for context
     b. Call Claude API (claude-haiku-4-5):
        - What is abnormal and by how much
        - When it started (first divergence point)
        - What operations / tenants are affected
        - Likely cause given ShelfOps architecture
        - What to check first
     c. Write anomaly_event to DB
     d. POST to Slack if severity >= 'medium'
  6. Low-severity anomalies (z < 3, isolated) → written to DB only, no Slack.
     Weekly digest summarizes these.
```

### Weekly Digest Task: `workers.observability.weekly_digest`

Schedule: Monday 06:00 UTC (after backtest-weekly completes)

```
Queries:
  - error_events last 7 days: count by type, recurring vs. new
  - anomaly_events last 7 days: count by type and severity
  - Resolution rate: % of error_events with resolved_at set

Sends Slack message:
  "Week of [date]: N errors (M new types), P anomalies, Q resolved.
   Top issue: [most frequent error type]. Still open: [unresolved list]."
```

---

## Frontend Changes

None in this phase. The Slack delivery is the UI. A future dashboard card showing
`open_anomalies` count and recent error timeline would be Phase B.

---

## Structured Logging Configuration

`structlog` is already imported in `main.py` but not configured. The setup belongs in
`backend/core/observability.py` and called once at app startup.

**Key processors**:
- `structlog.contextvars.merge_contextvars` — picks up tenant_id and request_id bound
  per-request via `structlog.contextvars.bind_contextvars()`
- `structlog.processors.TimeStamper(fmt="iso")` — ISO8601 timestamps
- `structlog.processors.JSONRenderer` in production, `structlog.dev.ConsoleRenderer` in local
- Custom `DBSinkProcessor` — async write to `log_events` table for warning+ events

**Context binding points**:
- API middleware: bind `request_id` (UUID4) and `tenant_id` at request start, clear at end
- Celery tasks: bind `task_id` and `tenant_id` at task entry via `@app.task` base class

**Log levels written to DB**: `warning`, `error`, `critical` only.
`debug` and `info` go to stdout only (too high volume for DB sink).

---

## Files to Create

| File | Description |
|---|---|
| `backend/core/observability.py` | structlog configuration, context binders, DB sink processor |
| `backend/api/middleware/error_tracking.py` | FastAPI exception handler, error_events writer, fingerprint computation |
| `backend/workers/tasks/observability.py` | All three Celery tasks: diagnose_error, detect_log_anomalies, weekly_digest |
| `alembic/versions/add_observability_tables.py` | Migration for error_events, log_events, anomaly_events |

## Files to Modify

| File | Change |
|---|---|
| `backend/core/config.py` | Add `slack_webhook_url`, `anthropic_api_key`, `observability_enabled: bool = True`, `anomaly_z_score_threshold: float = 2.5` |
| `backend/api/main.py` | Call `configure_observability()` in lifespan startup; register error tracking middleware |
| `backend/workers/celery_app.py` | Add `detect-log-anomalies-15m` and `weekly-digest-monday` to beat schedule; add `workers.observability.*` to task_routes |

---

## Auto-Fix Scope (Explicit Boundaries)

**In scope (this spec)**:
- Actionable fix text in the Slack message (user reads and applies manually)
- For `fix_type == 'env'` or `fix_type == 'config'`: the Slack message includes the exact
  env var name and suggested value

**Explicitly out of scope (future)**:
- Automated code change or PR creation
- Automated restart of failed Celery tasks
- Self-healing DB repair

The fix loop is: LLM proposes → human applies → mark resolved. Auto-applying code changes
requires more trust in the LLM output quality than this first version warrants.

---

## Test Plan

**Unit tests** (`backend/tests/test_observability.py`):
- Fingerprint computation is deterministic for same error type + stack frames
- Dedup logic: second identical error within 30 min does not queue a new diagnosis task
- Z-score anomaly detection flags correctly on synthetic log data with injected spike
- Slack payload structure matches expected schema (mock webhook)
- LLM diagnosis task handles Claude API timeout gracefully (falls back to raw stack trace delivery)

**Integration tests**:
- Raise a deliberate exception in test endpoint → verify error_event written to DB with correct
  tenant_id, fingerprint, and request_path
- Inject 50 error log_events in a 15-min window → verify anomaly_events row created
- Verify structlog context (tenant_id, request_id) propagates correctly through middleware chain

**Edge cases**:
- Error in a Celery task with no tenant_id (global job) — `tenant_id` is NULL, not errored
- Claude API is unavailable — error is still written to DB and sent to Slack without diagnosis
  (raw stack trace only, with "LLM diagnosis unavailable" note)
- Error fingerprint collides (hash collision) — acceptable, treat as duplicate; collision rate
  is negligible for sha256 truncated to 16 bytes

---

## Out of Scope

- Sentry, Datadog, or any external observability SaaS
- Distributed tracing (OpenTelemetry spans)
- Frontend error tracking (React error boundaries, JS exceptions)
- Real-time dashboard in the ShelfOps UI (Phase B)
- Auto-PR creation for LLM-proposed code fixes

---

## Complexity Estimate

**L — 1–2 days**

Breakdown:
- DB migration + TimescaleDB setup: S
- `observability.py` structlog config + DB sink: S
- Error tracking middleware: S
- `diagnose_error` Celery task + Claude integration + Slack delivery: M
- `detect_log_anomalies` Celery task + IsolationForest + LLM: M
- Context binding in API middleware and Celery base task: S
- Tests: S
