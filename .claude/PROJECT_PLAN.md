# ShelfOps — Pre-Demo Project Plan

- Status: **Active — Sprints 1 + 2 complete; Sprint 3 in progress (Shepherd.js next)**
- Created: February 2026
- Branch: `claude/analyze-codebase-FEu8K`
- Source of truth for P0 items: `docs/BRAINSTORM.md §19` + `.claude/DEMO_PLAN.md §9`

Each item follows the protocol from `CLAUDE.md`:
`/spec` → implement + tests → `/test-loop` until green → commit → check off in BRAINSTORM.md §19

---

## Audit: What Needs to Be Done Before Demo

Cross-referencing `BRAINSTORM.md §19 P0` with `DEMO_PLAN.md §9`.
All items below are unchecked and unbuilt as of February 2026.

---

## Workstreams

### WS-1: Data Foundation
**Must be first — all other workstreams depend on a loaded, realistic demo state.**

| # | Item | File(s) | Test requirement | Status |
|---|---|---|---|---|
| 1.1 | Demo dataset — 50 SKUs, engineered patterns (seasonal spike, Black Friday lift, vendor incident) | `data/demo/*.csv`, `data/demo/README.md`, `data/demo/demo_tenant.json` | Pandera validates each CSV on load | ✅ Done |
| 1.2 | `seed_demo.py` — idempotent script; loads full Day 95 state including shadow challenger, open alerts, 1 pending PO | `data/demo/seed_demo.py` | Run twice → same DB state; test checks idempotency | ✅ Done |

**Definition of done**: `python data/demo/seed_demo.py` on a fresh DB produces exactly the Day 95 state described in `DEMO_PLAN.md §4`.

---

### WS-2: Backend ML
**Dependency**: WS-1 (demo dataset needed to test model quality)
**Order matters within WS-2**: LightGBM switch → metrics → pre-trained model → timezone → locks/cleanup → CI test

| # | Item | File(s) | Why P0 | Test requirement | Status |
|---|---|---|---|---|---|
| 2.1 | LightGBM switch — LSTM weight → 0.0 | `backend/ml/train.py`, `backend/ml/ensemble.py` | LSTM actively degrades every metric; demo would show a worse model | `test_model_quality_ci.py` MASE < 1.0 | ✅ Done |
| 2.2 | WAPE + MASE metrics — replace MAPE | `backend/ml/metrics.py`, `backend/ml/arena.py` | Current metrics mislead; demo numbers look bad even if model is good | Unit tests: WAPE/MASE on known series; Arena gates read correct metric | ✅ Done |
| 2.3 | Pre-trained LightGBM on Favorita + M5 | `backend/ml/pretrain.py` (new), `data/pretrain/` | Cold-start on 27 rows is not demoable | MASE < 1.0 on holdout before any tenant data | ⬜ Not started |
| 2.4 | Timezone-aware feature engineering | `backend/ml/features.py` | All temporal features (DoW, hour, seasonality) wrong for non-Eastern tenants | Test: UTC tenant and PST tenant produce different lag features for same wall-clock time | ✅ Done |
| 2.5 | Redis retrain lock | `backend/workers/retrain.py` | Concurrent retrains corrupt `ModelVersion` state | Test: two simultaneous retrain calls; only one proceeds, second returns 409 | ✅ Done |
| 2.6 | Retrain failure → `status = failed` | `backend/workers/retrain.py` | Orphaned `training` records block all subsequent retrains | Test: inject exception mid-retrain; verify `ModelVersion.status = failed` not `training` | ✅ Done |
| 2.7 | Model quality regression test in CI | `backend/tests/test_model_quality_ci.py` (new) | Can't demo without knowing the model is good after any code change | Test itself — runs full train loop on demo dataset; asserts MASE < 1.0 | ✅ Done |

---

### WS-3: Backend API
**Dependency**: WS-2 (model must be trained before SHAP is computable)

| # | Item | File(s) | Why P0 | Test requirement | Status |
|---|---|---|---|---|---|
| 3.1 | SHAP endpoint `GET /forecasts/{id}/explain` | `backend/api/v1/routers/forecasts.py` | Used in both Shepherd tours; product detail UI reads it | `test_forecasts_explain_api.py`: valid response, Redis cache hit, tenant isolation (Tenant B cannot read Tenant A's SHAP) | ✅ Done |

---

### WS-4: Frontend
**Dependency**: WS-3 (API must exist before UI reads it); WS-1 (seed data produces realistic values)
**Order within WS-4**: Activity Feed + Events Panel first (tours depend on them) → SHAP waterfall → rest

| # | Item | File(s) | Why P0 | Test requirement | Status |
|---|---|---|---|---|---|
| 4.1 | Platform Activity Feed | `frontend/src/components/dashboard/ActivityFeed.tsx` | Core demo step 1/2; makes invisible ML pipeline visible | Renders from `ModelVersion` + retrain log; shows Day 95 state entries | ✅ Done — mounted on DashboardPage |
| 4.2 | System Events Panel (WebSocket drawer) | `frontend/src/components/dashboard/SystemEventsPanel.tsx` | Core demo step 6/7; shows real-time backend events after buyer action | Opens on PO approve/disapprove; receives WebSocket event; displays `rejection_rate_30d` update | ✅ Done — mounted on DashboardPage; auto-expands on `?tour=technical`; sets `window.__demoEventReceived` |
| 4.3 | SHAP waterfall UI | `frontend/src/components/forecasts/SHAPWaterfall.tsx` | Demo step 3/4; most compelling explainability visual | Renders on "Why this forecast?" click; horizontal bar chart via Recharts; plain-language labels | ✅ Done — wired into ForecastsPage top movers |
| 4.4 | Model improvement timeline | `frontend/src/components/dashboard/ModelTimeline.tsx` | Demo step 8; shows MASE 0.95 → 0.71 journey visually | Sparkline + event annotations (Day 44 graduation, Day 57 shadow start) | ✅ Done — mounted on DashboardPage |
| 4.5 | Graduation notification | `frontend/src/components/notifications/GraduationToast.tsx` | Demo narrative requires showing milestone firing | Toast/badge fires when `ModelVersion.status` transitions to `champion` | ✅ Built — not yet wired to WS graduation event |
| 4.6 | Data freshness banner | `frontend/src/components/layout/DataFreshnessBanner.tsx` | Silent stale data failure would undermine demo trust | Banner appears when last sync gap > 48h; suppresses forecast confidence indicators | ✅ Built — not mounted (no stale-data scenario in demo) |
| 4.7 | Welcome modal | `frontend/src/components/demo/WelcomeModal.tsx` | Entry point for both demo tracks | Shows on first load (session storage flag); two buttons route to buyer/technical tour | ✅ Done — mounted in `ModernDashboardLayout` |
| 4.8 | Mode switching (`?tour=buyer` / `?tour=technical`) | `frontend/src/hooks/useDemoMode.ts` | Buyer mode hides ML details; technical mode exposes them | URL param read on load; context propagates to all components; System Events Panel open by default in technical mode | ✅ Done — hook wired into SystemEventsPanel, SHAPWaterfall, DashboardPage, ForecastsPage |

---

### WS-5: Demo Infrastructure — Shepherd.js Tours
**Dependency**: WS-4 (all frontend components must exist before tours point at them)
**Dependency**: WS-2 + WS-3 (WebSocket events must fire for reactive step to work)

| # | Item | File(s) | Why P0 | Test requirement | Status |
|---|---|---|---|---|---|
| 5.1 | Shepherd.js install | `frontend/package.json` | Library dependency | `npm run build` passes | ⬜ Not started |
| 5.2 | Buyer tour — 8 steps per `DEMO_PLAN.md §6` | `frontend/src/tours/buyerTour.ts` (new) | Track A demo | Each step renders; `advanceOn` for disapprove click; step 6 only shows after WebSocket flag | ⬜ Not started |
| 5.3 | Technical tour — 9 steps per `DEMO_PLAN.md §7` | `frontend/src/tours/technicalTour.ts` (new) | Track B demo | Same reactive step; Arena gate panel renders; GitHub links present | ⬜ Not started |
| 5.4 | Reactive step (WebSocket flag polling) | `frontend/src/tours/demoEvents.ts` (new) | Tours must feel live; step fires when real event arrives, not on Next click | `beforeShowPromise` resolves only after `window.__demoEventReceived` set by WS handler | ⬜ Not started |

---

### WS-6: Splash / Entry Route
**Dependency**: WS-5 (tours must work before splash routes into them); GIF clips added after recording

| # | Item | File(s) | Why P0 | Test requirement | Status |
|---|---|---|---|---|---|
| 6.1 | `/welcome` route | `frontend/src/pages/WelcomePage.tsx` (new) | Entry point context; two CTA buttons with `?tour=` params | Route exists; buttons have correct hrefs; mobile-responsive | ⬜ Not started |

---

### WS-7: API Test Coverage (Demo-Blocking)
**Can run in parallel with WS-4/WS-5 once WS-3 is done**

| # | Item | File(s) | Endpoints covered | Status |
|---|---|---|---|---|
| 7.1 | `test_forecasts_explain_api.py` | `backend/tests/test_forecasts_explain_api.py` | `GET /forecasts/{id}/explain` — valid, cached, tenant isolation | ✅ Done |
| 7.2 | `test_outcomes_api.py` | `backend/tests/test_outcomes_api.py` | ROI endpoint — stockouts avoided, revenue protected; tenant scoped | ✅ Done |
| 7.3 | `test_reports_api.py` | `backend/tests/test_reports_api.py` (new) | `stockout-risk`, `inventory-health`, `forecast-accuracy` | ⬜ Not started |

---

## Dependency Graph

```
WS-1 (Demo Dataset + Seed)
  └─→ WS-2 (Backend ML: LightGBM, WAPE/MASE, pretrain, timezone, locks, CI)
        └─→ WS-3 (SHAP API endpoint)
              ├─→ WS-4 (Frontend: 8 components)
              │     └─→ WS-5 (Shepherd.js tours)
              │           └─→ WS-6 (/welcome route)
              └─→ WS-7 (API tests — can parallel WS-4+)
```

---

## Execution Order (Sprint Sequence)

### Sprint 1 — Foundation + Backend ML ✅ Complete (except 2.3)
**Goal**: Model is switched, metrics are honest, CI gate in place.
Items: 1.1 ✅, 1.2 ✅, 2.1 ✅, 2.2 ✅, 2.3 ⬜, 2.4 ✅, 2.5 ✅, 2.6 ✅, 2.7 ✅

### Sprint 2 — API + Core Frontend ✅ Complete
**Goal**: SHAP endpoint live, feed + panel + waterfall built.
Items: 3.1 ✅, 4.1 ✅, 4.2 ✅, 4.3 ✅, 7.1 ✅, 7.2 ✅, 7.3 ⬜

### Sprint 3 — Remaining Frontend + Demo Infrastructure 🔄 In Progress
**Goal**: All UI components built; tours wired; entry point live.
Items: 4.4 ✅, 4.5 ✅, 4.6 ✅, 4.7 ✅, 4.8 ✅, 5.1 ⬜, 5.2 ⬜, 5.3 ⬜, 5.4 ⬜, 6.1 ⬜
**Remaining**: Install Shepherd.js (5.1) → buyer tour (5.2) → technical tour (5.3) → reactive step (5.4) → /welcome route (6.1)

---

## Checklist Status vs. BRAINSTORM.md §19

When each item ships, check it off both here AND in `docs/BRAINSTORM.md §19`.

| BRAINSTORM §19 P0 item | PROJECT_PLAN item | Status |
|---|---|---|
| LightGBM switch | 2.1 | ✅ Done |
| WAPE + MASE metrics | 2.2 | ✅ Done |
| Pre-trained model on Favorita + M5 | 2.3 | ⬜ Not started |
| Timezone-aware feature engineering | 2.4 | ✅ Done |
| Model improvement history in UI | 4.4 | ✅ Done |
| Graduation event notification | 4.5 | ✅ Built (WS trigger pending) |
| Data freshness UI banner + suppression | 4.6 | ✅ Built (not mounted — no stale scenario) |
| Concurrent retrain Redis lock | 2.5 | ✅ Done |
| Retrain failure → `status = failed` | 2.6 | ✅ Done |
| Model quality regression test in CI | 2.7 | ✅ Done |
| SHAP waterfall in product detail UI | 4.3 | ✅ Done |

---

## How to Use This Plan

Each sprint, pick the next unchecked item in order. Then:

1. Run `/spec` — draft the technical spec before touching code
2. Implement with tests alongside (not after)
3. Run `/test-loop` — repeat until all gates green
4. Commit with descriptive message, push to branch
5. Check off item in this file AND in `docs/BRAINSTORM.md §19`
6. Confirm test count is ≥ 497: `PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | tail -5`
