# ShelfOps — Demo Readiness Plan

- Status: **Active — work in progress**
- Updated: February 2026
- Context: Scripted demo using existing seed data. No company data available.
  No rush — getting demo-ready, not demoing now.

---

## 1. What We Are Building Toward

A single scripted walkthrough that tells two coherent stories in sequence.
One codebase, one demo environment, two narrative tracks.

### Audience A — Hiring Managers / Technical Interviewers

They want to see engineering depth and ML rigor. Key questions they're evaluating:
- "Can this person build production ML, not just notebooks?"
- "Does the system have real observability and correctness guarantees?"
- "Is multi-tenancy actually enforced or just claimed?"

What resonates: Arena 7-gate promotion system, shadow/canary testing, SHAP
explainability, Pandera validation gates, MLflow experiment tracking, Celery pipeline
architecture, 497+ tests, feature engineering tier selection.

**Existing asset**: `docs/demo/recruiter_demo_runbook.md` + `backend/scripts/run_recruiter_demo.py`
This track already exists in partial form. It needs to be extended to showcase the
Celery task chain and live Arena/shadow testing (see §4).

### Audience B — Buyers / Operators (SMB Retail)

They want to see value, not architecture. Key questions:
- "Will this actually catch stockouts before they happen?"
- "Can my team understand why it made a recommendation?"
- "How do I know the model is getting better over time?"

What resonates: stockout alert → PO recommendation → "saved $2,400", SHAP waterfall
("here's why"), model improvement timeline ("your accuracy improved 23% since
onboarding"), ROI dashboard.

**Existing asset**: None. This track needs to be built from scratch.

---

## 2. Demo Architecture — Scripted Auto-Trigger Chain

The challenge: we want to *show* the Celery auto-triggers without running the platform
for 90 real days. The solution: a time-warp orchestration script that seeds data at
different temporal stages and fires each pipeline step in sequence with visible output.

### The Event Chain to Show

```
[STEP 1]  Tenant onboarded
          → cold-start model loaded (pre-trained on Favorita + M5)
          → first forecast issued (honest confidence)

[STEP 2]  30 days of transaction data seeded (fast-forward)
          → milestone_check Celery task fires
          → 30-day density check passes
          → shadow training job queued + executes
          → Arena gate 1-7 evaluation runs
          → if passes: challenger promoted to champion
          → graduation notification generated ("Model updated with your data")

[STEP 3]  Demand spike injected for SKU-X (anomaly)
          → Isolation Forest: anomaly_score > threshold
          → 3rd consecutive day: structural_shift_detected
          → drift_retrain Celery task auto-fires
          → new shadow model queued (can show in real time)

[STEP 4]  Stockout risk surfaced
          → stockout-risk API called
          → PO recommendation generated
          → buyer "approves" PO in the UI
          → outcome recorded: stockout_avoided

[STEP 5]  ROI dashboard
          → GET /outcomes/roi
          → "1 stockout avoided · $2,400 estimated savings"
```

### How to Implement This

The orchestration script (`backend/scripts/run_buyer_demo.py`, to be created) will:
1. Set `APP_ENV=demo` and point at a local DB with seeded fixture data
2. Call each step via direct Python function calls (Celery tasks in ALWAYS_EAGER mode
   for demo) or subprocess calls to the existing seed/trigger scripts
3. Print structured progress output (step name, timing, what fired, what the result was)
4. The buyer demo script should produce a markdown summary similar to the recruiter
   scorecard, but in plain language

For Celery tasks in demo mode:
- Set `CELERY_TASK_ALWAYS_EAGER=True` in the demo environment
- This runs tasks synchronously, inline, with visible output — no broker needed
- Each task's result is captured and printed as the "auto-trigger" fires

---

## 3. Technical Pre-Work — What Must Be Built

Ordered by priority. Each item must be tested to green before moving on.
See §5 for the test discipline rules.

### P0 — Required for the demo to not be broken or embarrassing

| # | Item | Why | Files | Complexity |
|---|---|---|---|---|
| 1 | **Switch to pure LightGBM** (zero LSTM weight) | LSTM degrades every metric — demo shows a worse model | `ml/features.py`, `workers/retrain.py`, `ml/arena.py` | M |
| 2 | **WAPE + MASE replacing MAPE** | MAPE is misleading near zero demand; metrics look bad even when model is good | `ml/metrics.py`, `ml/arena.py`, reports | S |
| 3 | **Train pre-trained model on full Favorita + M5** | Cold-start model was trained on 27 rows — not demoable | `scripts/download_kaggle_data.py`, `scripts/run_training.py` | M |
| 4 | **SHAP endpoint + waterfall UI** | Most compelling explainability visual; currently broken (not in API or UI) | New endpoint `GET /forecasts/{id}/explain`, `ProductDetailPage.tsx` | L |
| 5 | **Model improvement history UI** | Core "value proof" moment; data exists in DB, no UI surface | Dashboard component, `GET /ml_ops/models` wired to timeline | M |
| 6 | **Graduation event notification** | The milestone-fires moment is the demo's "wow" — needs to be visible | Celery task output, notification model, UI badge | M |
| 7 | **Data freshness UI banner** | Stale demo data silently shows wrong forecasts — trust killer | `data_freshness_check` Celery job + UI suppression banner | S |
| 8 | **Retrain orphan cleanup** (`status = failed`) | Orphaned `training` records silently block subsequent retrains | `workers/retrain.py` error handler | S |
| 9 | **Redis lock for concurrent retrains** | Two simultaneous retrains corrupt `ModelVersion` state | `workers/retrain.py` lock acquire/release | S |
| 10 | **Model quality regression test in CI** | Can't demo if a code change broke the model between sessions | `tests/test_model_quality_ci.py` | S |

### P1 — Required before first customer, not demo-blocking

| # | Item | Section |
|---|---|---|
| 11 | Milestone triggers (30/90/180/365d) with density check | BRAINSTORM §2.3 |
| 12 | Feedback quality filter (reason codes) | BRAINSTORM §3.3 |
| 13 | PO suggestion override cache | BRAINSTORM §3.2 |
| 14 | Staging environment (GCP Cloud Run) | BRAINSTORM §10.2 |
| 15 | RLS CI lint rule (block `get_db` in routers) | BRAINSTORM §13.1 |
| 16 | Arena per-segment evaluation | BRAINSTORM §6.2 |
| 17 | Champion minimum hold period (14d) | BRAINSTORM §6.1 |
| 18 | Webhook dead-letter queue | BRAINSTORM §10.4 |

### P2 — Post-demo, post-launch

See `docs/BRAINSTORM.md §19` for the full P2/P3 lists.

### API test coverage (from §23 audit)

These 32 untested endpoints should be covered before first customer.
For demo: cover at minimum the P1 endpoints in `§23.1` (ROI, SHAP, stockout-risk,
inventory-health). Run the test-loop command for each.

---

## 4. Demo Script Architecture — Two-File Design

```
backend/scripts/
├── run_recruiter_demo.py    ← EXISTS: extend with Celery chain + shadow testing
└── run_buyer_demo.py        ← NEW: buyer narrative, time-warp orchestration

docs/demo/
├── recruiter_demo_runbook.md ← EXISTS: update to reflect new capabilities
└── buyer_demo_runbook.md     ← NEW: step-by-step buyer walkthrough
```

### `run_buyer_demo.py` — What It Does

```
python3 backend/scripts/run_buyer_demo.py [--quick] [--output-dir ./demo_output]
```

Steps (each prints a visible header):
1. `[ONBOARDING]` — seed tenant + initial data, show cold-start forecast
2. `[30-DAY MILESTONE]` — seed 30d transactions, fire milestone check, show Arena gates
3. `[GRADUATION]` — show champion promotion event + notification
4. `[DRIFT EVENT]` — inject anomaly, show structural shift detection + auto-retrain
5. `[STOCKOUT ALERT]` — show stockout-risk report, PO recommendation
6. `[BUYER ACTION]` — simulate PO approval + outcome recording
7. `[ROI SUMMARY]` — show ROI endpoint output in plain language

Output: `buyer_demo_scorecard.md` in the output dir (mirrors recruiter scorecard format).

### Extending `run_recruiter_demo.py`

Add two new sections between strategy cycle and replay:
- **Celery pipeline visualization**: call each scheduled task type explicitly, capture
  and print what fired and why (showing the 12 scheduled jobs architecture)
- **Shadow model walkthrough**: show a challenger being evaluated through all 7 Arena
  gates, with per-gate pass/fail output

---

## 5. Test Discipline — Non-Negotiable Rules

Every feature on the P0/P1 list above follows this cycle before it is considered done:

1. **Write a spec first** — use `/spec` command to draft the spec before touching code
2. **Write tests alongside the implementation** — never ship an untested feature
3. **Run `/test-loop`** — run tests, fix failures, re-run until fully green
4. **No demo-only hacks in production code** — if a shortcut is needed for the demo,
   it goes in the demo script, not in the API or ML pipeline code
5. **Each P0 item gets a dedicated commit** — one item per commit, clear message,
   pushed to `claude/analyze-codebase-FEu8K`

### The Test Loop Command

```bash
PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | head -200
```

For a specific new test file:
```bash
PYTHONPATH=backend pytest backend/tests/test_{new_file}.py -v --tb=short
```

Current baseline: **497 tests passing**. Every session should end with ≥ 497 passing.
If a commit breaks tests, fix before next task.

---

## 6. Demo Data Strategy

### What Exists

- `data/seed/` — Favorita/M5/Rossmann training datasets
- `backend/scripts/seed_test_data.py` — basic test data seeder
- `backend/scripts/seed_commercial_data.py` — commercial tenant seeder
- `backend/scripts/seed_forecasts.py` — forecast data seeder
- `backend/scripts/bootstrap_square_demo_mapping.py` — Square POS demo mapping

### What Needs to Be Created

A **demo-specific seed dataset** that supports the buyer narrative arc:

```
data/demo/
├── demo_tenant.json          ← tenant config (single SMB retailer, ~50 SKUs)
├── day_000_snapshot.csv      ← onboarding state (30d history, cold-start)
├── day_030_transactions.csv  ← 30 days of sales (triggers first milestone)
├── day_090_transactions.csv  ← additional 60 days (triggers graduation)
├── anomaly_event.csv         ← 3-day demand spike on SKU-X
└── README.md                 ← describes the fictional retailer and its SKUs
```

The fictional retailer: a specialty outdoor gear shop, ~50 SKUs, mix of fast-movers
(water bottles, sunscreen) and slow-movers (tents, kayak paddles). Clear seasonality.
This gives us interesting SHAP stories ("summer promo event: +40% demand driver").

### Avoiding Real Company Data

All seed data is either:
- Transformed public datasets (Favorita/M5 product names → outdoor gear names)
- Synthetically generated from realistic distributions
- The existing `seed_*` scripts extended with demo-specific parameters

---

## 7. SHAP Implementation — Critical Path Detail

This is the most complex P0 item and is currently completely missing from the stack.
Do not skip this — it is the single most compelling visual for both audiences.

### Backend Work

1. New endpoint: `GET /api/v1/forecasts/{forecast_id}/explain`
   - Loads champion model for tenant
   - Reconstructs feature vector for the forecast
   - Runs `shap.TreeExplainer` (LightGBM after P0 item #1)
   - Returns `{feature: signed_shap_value}` dict
   - Cache result in Redis: key `shap:{forecast_id}:{model_version}`, TTL 1 hour

2. Schema: `ForecastExplainResponse` — separate from `ForecastResponse`
   (SHAP not included in bulk forecast queries — too expensive)

3. Add `tests/test_forecasts_explain_api.py`:
   - Response structure matches schema
   - Tenant isolation (Tenant B cannot explain Tenant A's forecast)
   - Feature names in response match current feature set (drift guard)
   - Redis cache is populated on first call, served on second call
   - Handles cold-start gracefully (no champion model → 404 with reason)

### Frontend Work

In `ProductDetailPage.tsx`:
- Collapsible "Why this forecast?" panel below the forecast chart
- Horizontal bar chart (Recharts): positive bars = demand drivers, negative = suppressors
- Sorted by absolute SHAP value descending
- Top 8 features shown, "show more" expands to all
- Plain-language labels: `rolling_7d_avg` → "7-day sales trend"

---

## 8. Model History UI — Critical Path Detail

### Backend Work (already exists, just needs wiring)

`GET /api/v1/ml_ops/models` — returns `ModelVersion` list. Already implemented.
`GET /api/v1/reports/forecast-accuracy` — currently **untested** (§23 audit).

Add tests for `reports.py`:
- `test_reports_api.py` covering forecast-accuracy, inventory-health, stockout-risk
- Specifically: accuracy trend returns values in time order, empty for tenant with no history

### Frontend Work (new component)

On the main dashboard:
- **Model Health card**: current MASE + sparkline (90 days). Arrow up/down.
  Plain language: "Forecast accuracy improved 23% since onboarding."
- **Timeline component**: key events in chronological order:
  - "Onboarded: cold-start model active"
  - "30-day milestone: first model trained on your data (MASE: 0.87)"
  - "90-day graduation: model updated (MASE: 0.71) ↑ 18% improvement"
  - "Drift detected: model auto-updated (MASE: 0.68)"

This is the "your model is getting better" story that justifies the subscription.

---

## 9. Session Handoff — What Future Sessions Should Know

When a new session picks up this plan:

1. **Read this file first**
2. **Check BRAINSTORM.md §19** for the full P0/P1 priority context
3. **Run the test suite** to confirm the current green baseline:
   ```bash
   PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | tail -20
   ```
4. **Pick the next unchecked P0 item** from §3 above and use `/spec` to draft
   the spec before starting implementation
5. **Use `/test-loop` after each implementation** until fully green
6. **Commit each item separately** with a clear message, push to `claude/analyze-codebase-FEu8K`

### Current State (February 2026)

- [x] BRAINSTORM.md — comprehensive, 25 sections, living document
- [ ] P0 item #1 — LightGBM switch (not started)
- [ ] P0 item #2 — WAPE + MASE metrics (not started)
- [ ] P0 item #3 — Pre-trained model on full Favorita + M5 (not started)
- [ ] P0 item #4 — SHAP endpoint + UI (not started — highest complexity)
- [ ] P0 item #5 — Model history UI (not started)
- [ ] P0 item #6 — Graduation event notification (not started)
- [ ] P0 item #7 — Data freshness banner (not started)
- [ ] P0 item #8 — Retrain orphan cleanup (not started)
- [ ] P0 item #9 — Redis retrain lock (not started)
- [ ] P0 item #10 — Model quality CI test (not started)
- [ ] Demo data seed dataset (not started)
- [ ] `run_buyer_demo.py` script (not started)
- [ ] API test coverage for 32 untested endpoints (not started)

---

## 10. Open Decisions

These need answers before the corresponding implementation starts:

- [ ] **SHAP feature labels**: what mapping from internal feature names (`rolling_7d_avg`,
  `lead_time_days`) to buyer-friendly labels ("7-day sales trend", "Supplier lead time")?
  This lives in a config file, not hardcoded. Where does the config file live?

- [ ] **Demo retailer profile**: outdoor gear shop (current suggestion) vs. something else?
  The fictional business type determines which SHAP features will be most interesting.

- [ ] **Graduation notification UX**: in-app toast, persistent notification bell, or
  email? For demo purposes, an in-app badge is sufficient. Real decision can wait.

- [ ] **Buyer demo script format**: pure terminal output (like recruiter demo), or
  should it drive a live browser session (Playwright/Selenium for UI)? Terminal is
  simpler and more reliable for a scripted demo. Browser automation is more visually
  compelling but more fragile.
