# Workflow: Phase 3 — Testing & Quality

**Purpose**: Achieve test coverage targets and pass CI for Phase 3 completion
**Agent**: qa-engineer (tests), full-stack-engineer (API), ml-engineer (ML tests)
**Duration**: 1-2 days

## Prerequisites

- Phase 1, 2, 2.5 complete
- `PYTHONPATH=backend pytest backend/tests/ -v` runs without import errors
- `docker-compose up db redis` running

---

## Phase 1: Audit Existing Tests

```bash
PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | tail -30
```

Identify: pass / fail / error count, which test files exist, which modules lack coverage.
Fix import errors first — they block everything else.

Existing test files (19):
`test_api.py`, `test_stores_api.py`, `test_products_api.py`, `test_forecasts_api.py`,
`test_alerts_api.py`, `test_inventory_api.py`, `test_purchase_orders_api.py`,
`test_integrations_api.py`, `test_inventory_optimizer.py`, `test_supply_chain.py`,
`test_sourcing.py`, `test_ml_pipeline.py`, `test_retail_calendar.py`,
`test_shrinkage.py`, `test_planogram.py`, `test_reorder_constraints.py`,
`test_counterfactual.py`, `test_bugfixes.py`, `conftest.py`

---

## Phase 2: Fix Failing Tests

Run `/test-loop` per failing test file. Fix in order:
1. Import errors (fastest, unblocks other tests)
2. Fixture errors (`conftest.py` issues)
3. Logic failures (real bugs)

---

## Phase 3: Fill Coverage Gaps

Priority modules not yet covered:
- `backend/ml/feedback_loop.py` — PO rejection → ML feedback
- `backend/workers/vendor_metrics.py` — 90-day reliability scorecard
- `backend/retail/promo_tracking.py` — actual vs expected lift
- `backend/integrations/edi_adapter.py` — EDI X12 parsing

Use `test_db` or `seeded_db` fixtures from `conftest.py`. Do not add TimescaleDB-specific SQL.

---

## Phase 4: Linting

```bash
ruff check backend/ --config pyproject.toml
ruff format --check backend/ --config pyproject.toml
```

---

## Phase 5: Frontend

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

---

## Checklist

- [ ] All 19 existing test files pass
- [ ] Coverage added for feedback_loop, vendor_metrics, promo_tracking, edi_adapter
- [ ] `ruff check` passes with zero errors
- [ ] `ruff format --check` passes
- [ ] `npm run lint` passes
- [ ] `npm run build` passes
- [ ] CI pipeline passes on a feature branch push
