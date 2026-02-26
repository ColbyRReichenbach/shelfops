# ShelfOps — Demo Readiness Plan

- Status: **Active — Frontend P0 complete; Shepherd.js tours next**
- Updated: February 2026
- Branch: `claude/analyze-codebase-FEu8K`

---

## 1. Goal

Build a scripted, self-contained demo of ShelfOps using the live app + Shepherd.js
guided tours. No separate portfolio site. The ShelfOps app itself is the demo,
pre-loaded with the Summit Outdoor Supply dataset.

Two audiences, two Shepherd.js tour tracks, one deployment.

---

## 2. Audiences

### Track A — SMB Buyer
Retail ops lead or owner. Not technical. Evaluating whether the product catches
stockouts, explains itself, and proves its value over time.

Core questions they're asking:
- Will it actually catch problems before they happen?
- Can I understand why it made a recommendation?
- How do I know it's getting better?

### Track B — Hiring Manager / Technical Evaluator
Senior engineer or ML lead at a large company. Evaluating engineering depth and
production ML judgment.

Core questions they're asking:
- Is this production ML or a notebook dressed up?
- Is multi-tenancy actually enforced?
- Does the model governance system have real rigor?
- What's enterprise-ready vs. roadmap?

---

## 3. Demo Format

### Primary Surface: Live App + Shepherd.js

The ShelfOps frontend IS the demo. Pre-loaded with Summit Outdoor Supply data
at Day 95 state (post-graduation, active shadow challenger in progress).

A welcome modal on first load presents two buttons:
- "Show me the buyer experience" → launches Buyer Tour
- "Show me the technical architecture" → launches Technical Tour

Shepherd.js drives each tour. Steps advance on user actions (not just "Next" clicks)
so the tour feels live, not scripted.

### Splash Page (Simple)

A single-page entry point before the app. Purpose: context + routing.
- 3-sentence product description
- Two track entry buttons (link directly into app with `?tour=buyer` or `?tour=technical`)
- 2–3 embedded GIF clips of the most visually striking moments
- Link to GitHub + "run it yourself" one-liner

Built as a `/welcome` route inside the existing React app. Same codebase, same
deployment. Not a separate site.

### Recording Format

Every tour recorded as a Loom: face cam (bottom-right corner) + screen + live voiceover.
Not word-for-word scripted — talking point bullets per step, spoken naturally.

Short GIF clips (30–60s each) cut from the full Loom recordings for the splash page.
Terminal sections recorded with Asciinema (text-based, hire managers can pause/copy).

---

## 4. Demo Dataset — Summit Outdoor Supply

A purpose-built synthetic dataset. Not real company data. Not raw Favorita.
Engineered to tell an interesting story with clear SHAP drivers.

**The fictional retailer**: single-location outdoor gear shop, ~50 SKUs.
Mix of fast-movers (water bottles, sunscreen, trail mix) and slow-movers
(tents, kayak paddles, climbing harnesses). Clear summer seasonality.
One Black Friday promo event. One supplier reliability incident (weeks 32–34).

**Engineered patterns**:
- Summer demand spike on kayak paddles → SHAP story: "seasonal driver +38%"
- Black Friday lift on apparel SKUs → SHAP story: "promo event +29%"
- Vendor X delivery failures weeks 32–34 → SHAP story: "supplier variance +15%"
- 3 historical near-stockout events the model would have caught
- A slow-mover SKU with intermittent demand (wide SHAP, uncertain forecast)

**Demo state at load (Day 95)**:
- Champion model: MASE 0.71 (graduated at Day 44 from cold-start 0.95)
- Active shadow challenger: MASE 0.64, trained with promo features
- Shadow challenger has been running 6 days, needs 8 more to auto-promote
- 3 open stockout alerts on fast-moving SKUs
- 1 PO recommendation pending buyer action

**File structure**:
```
data/demo/
├── README.md                    ← retailer description, SKU list, engineered patterns
├── demo_tenant.json             ← tenant config
├── transactions_day000_030.csv  ← onboarding period (cold-start)
├── transactions_day031_090.csv  ← graduation period
├── transactions_day091_095.csv  ← current period (with anomaly)
└── seed_demo.py                 ← one script to load full demo state into DB
```

`seed_demo.py` is idempotent — run it any time to reset to the canonical Day 95 state.

---

## 5. UI Components to Build

### 5.1 Platform Activity Feed

Always-visible panel on the dashboard (collapsible). Shows the chronological
history of everything the ML pipeline did automatically. This is the "behind
the scenes" story made visible.

```
⚙ Running in the background                    [last 95 days ▾]
─────────────────────────────────────────────────────────────────
Day 1    Tenant onboarded. Cold-start model activated.
         First forecasts issued: 50 SKUs

Day 30   Milestone: 30 days of data accumulated
         Challenger model trained automatically
         Arena: Gates 1–6 passed · Shadow period started

Day 44   Shadow canary held (14 days) ✓
         Champion promoted: MASE 0.95 → 0.71
         Accuracy improved 25%

Day 52   Demand spike: Kayak Paddle Pro (day 3 consecutive)
         Structural shift detected
         Auto-retrain triggered

Day 57   New challenger trained with promo features
         Arena: Gate 2 passed (MASE 0.71 → 0.64)
         Shadow phase started ● active

Today    Champion: MASE 0.71
         Shadow challenger: MASE 0.64 ● Day 6 of 14
         Auto-promotes in 8 days if shadow holds
```

Data source: reads from `ModelVersion`, retrain event log, anomaly alerts.
No new backend tables needed — just a new frontend component.

### 5.2 System Events Panel

Collapsible side drawer. Default: open in technical tour, closed in buyer tour.
Powered by the existing WebSocket infrastructure.

Shows a live event stream when buyer actions are taken:

| Buyer action | System Events panel shows |
|---|---|
| Click "Approve PO" | PODecision written · trust_score stable · feedback_loop queued |
| Click "Disapprove PO" | PODecision written · rejection_rate_30d ↑ · trust_score ↓ · Celery task queued |
| View a product forecast | SHAP computed (42ms) · cached in Redis (TTL: 1hr) |
| Page loads, data stale | data_freshness_check: 26h gap · WARNING banner triggered |
| Milestone fires | milestone_check passed · shadow_training queued · Arena starting |

This panel is what makes invisible background processes visible. Both tours use it
at the feedback loop step.

### 5.3 Welcome Modal

Appears on first load (session storage flag prevents repeat on refresh).
Two big buttons routing to each tour. Plain-language copy. No jargon.

### 5.4 Mode Switching

`?tour=buyer` or `?tour=technical` query param sets the demo mode:
- Buyer mode: hides MLflow details, Arena gate specifics; shows ROI prominently
- Technical mode: System Events panel open by default; SHAP shows raw feature names + friendly labels; Arena gate panel visible; links to GitHub/test files

---

## 6. Buyer Tour — Step by Step

**Shepherd.js, 8 steps. Plain language throughout. ~12 minutes.**

**Step 1 — Welcome / Activity Feed**
Tooltip on Platform Activity Feed:
> "Summit Outdoor Supply connected their Square POS 95 days ago. This is
> everything that happened automatically while they were running their shop."
Walk through the feed entries. Pause on the last line: active shadow challenger.
> "Right now, a better model is being quietly evaluated. If it holds for 8 more
> days, it auto-promotes. No one asked for this — it just runs."
[Next →]

**Step 2 — Today's Alerts**
Shepherd points to stockout alert card:
> "This alert fired automatically this morning. At current sales velocity,
> Kayak Paddle Pro has 2.8 days of stock left. Supplier lead time is 4 days.
> You're already behind if you don't act today."
[Next →]

**Step 3 — Why This Forecast?**
Tooltip on "Why this forecast?" button:
> "Click here to see exactly what's driving this prediction."
`advanceOn: { selector: '#shap-explain-btn', event: 'click' }`
→ SHAP waterfall panel loads.

**Step 4 — SHAP Waterfall**
Tooltip on the waterfall chart:
> "Summer seasonal demand is the biggest driver (+38%). You have a promo running
> on this SKU (+29%). Your supplier has had delivery delays recently (+15%).
> The model knows all of this. It's not a black box."
[Next →]

**Step 5 — PO Recommendation**
Shepherd points to PO recommendation card:
> "Based on that forecast, here's what the system recommends ordering and by when.
> You can approve it, adjust it, or push back entirely."
[Next →]

**Step 6 — Disapprove + Feedback Loop**
Tooltip on Disapprove button:
> "Let's say you disagree. Maybe you know the summer rush is over.
> Click Disapprove."
`advanceOn: { selector: '#po-disapprove-btn', event: 'click' }`
→ System Events panel slides in and lights up with events.

**Step 7 — System Events Panel**
Shepherd highlights the System Events panel (fires after the click):
> "Your decision was just recorded. The system updated your rejection rate for
> this SKU. At the next model update, your correction patterns become training
> features — the model learns your judgment, not just raw demand numbers."
Show: rejection_rate_30d updated, trust_score adjusted, Celery task queued.
[Next →]

**Step 8 — Model Improvement + ROI**
Shepherd points to Model Health card (accuracy sparkline):
> "MASE 0.95 on day 1. MASE 0.71 today. 25% more accurate — from 95 days of
> your actual data and 47 buyer corrections feeding back into training."
Then pan to ROI card:
> "This month: 3 stockouts avoided. $7,200 in prevented lost sales.
> That's the number."
[End of buyer tour]

**Enterprise coda (final slide, static):**
> "Summit Outdoor Supply is one store. The same platform handles multi-location
> chains — each location isolated, each with its own model, same pipeline.
> EDI X12 and SFTP enterprise integrations are in the codebase.
> Enterprise onboarding available."
Link → Technical tour for depth.

---

## 7. Technical Tour — Step by Step

**Shepherd.js, 9 steps. Implementation detail throughout. ~20 minutes.**

**Step 1 — Welcome**
Modal:
> "This tour covers the ML pipeline, model governance, multi-tenancy enforcement,
> and enterprise architecture. To run it yourself: one command, 497 tests."
Show GitHub link. [Start →]

**Step 2 — Platform Activity Feed (Technical Framing)**
Tooltip on Activity Feed:
> "This is the Arena log. Every entry was triggered automatically by the ML pipeline.
> The system is running a continuous champion/challenger architecture. There is always
> an active challenger being evaluated against the current champion."
Highlight the active shadow challenger entry.
[Next →]

**Step 3 — Arena: 7-Gate Evaluation**
Shepherd opens Arena gate panel (shows pre-computed gate artifact for current challenger):
> "A challenger doesn't promote just because it scores better on backtesting.
> It passes 7 gates."

Show gate-by-gate reveal (step-by-step animation):
```
Gate 1: Minimum rows          ✓  18,247 rows (min: 1,000)
Gate 2: MAE improvement       ✓  MASE 0.71 → 0.64  (−9.9%)
Gate 3: Stockout miss rate    ✓  4.2% → 3.1%
Gate 4: Overstock rate        ✓  8.7% → 7.2%
Gate 5: Overstock dollars     ✓  $12,400 → $9,800
Gate 6: SHAP stability        ✓  Top-5 features stable (Δ < 0.15)
Gate 7: Shadow canary (14d)   ⏳  Day 6 of 14 — auto-promotes in 8 days
```
> "Gate 6 is the one most systems skip. SHAP stability means the new model
> didn't just get lucky on the holdout — its feature importance structure is
> consistent with the champion. A model that passes Gates 1–5 but scrambles
> its feature weights is rejected."
[Next →]

**Step 4 — SHAP: Per-Prediction, Not Global**
Shepherd navigates to two different product detail pages.
First SKU (Kayak Paddle Pro):
> "Seasonality dominant. Summer pattern drives 38% of this forecast."
Second SKU (Climbing Harness):
> "Vendor reliability dominant. Supplier delivery variance is the biggest
> factor for this slow-mover. Same model, completely different story."
> "SHAP values here are per-prediction, computed at inference time.
> Not global feature importance — that's a much weaker claim."
[Next →]

**Step 5 — Feedback Loop: Buyer Corrections Become Features**
Navigate to PO screen.
> "The feedback loop is where this gets interesting. Watch what actually
> happens when a buyer pushes back on a recommendation."
Shepherd points to Disapprove button.
`advanceOn: { selector: '#po-disapprove-btn', event: 'click' }`
→ System Events panel lights up.

**Step 6 — System Events Panel (Technical)**
Shepherd highlights each event in the panel:
> "Three things just happened. A PODecision record was written with the outcome
> and quantity adjustment. rejection_rate_30d was recalculated for this SKU.
> forecast_trust_score was updated. A Celery task was queued to propagate this
> into the feature matrix at next retrain."
> "This is not logging. These are training features. The model learns the
> buyer's judgment pattern — not just raw demand signals."
Show the feature names: `rejection_rate_30d`, `avg_qty_adjustment_pct`,
`forecast_trust_score`. Link to `backend/ml/feedback_loop.py`.
[Next →]

**Step 7 — Multi-Tenancy: RLS Enforcement**
Shepherd navigates to a test evidence panel (or links to GitHub):
> "Multi-tenancy is enforced at the session level via SET LOCAL app.current_tenant.
> Every authenticated route uses get_tenant_db — not get_db. This is a codebase
> convention enforced by a CI lint rule."
Show test output from `test_security_guardrails.py`:
> "This test proves Tenant B gets zero rows from Tenant A's data.
> Not claimed in documentation — proven by a test that fails if violated."
[Next →]

**Step 8 — Enterprise Architecture**
> "The platform is SMB-GA. Enterprise architecture is designed in from the start."

What's production-ready:
- Multi-tenant RLS (every route)
- EDI X12 integration (transaction sets 846, 856, 810)
- Pandera validation at 3 gates (raw → features → predictions)
- Horizontal Celery worker architecture (Cloud Run target)
- Per-tenant MLflow namespacing (partial)

What's on the roadmap (honest):
- Native ERP connectors (SAP/Oracle/Dynamics — currently via SFTP/EDI)
- HA Celery scheduler (RedBeat — single beat process today)
- Staging environment (docker-compose local only today)
- Multi-region / data residency

> "I know what isn't built. The architecture is designed for it.
> The SMB path is production. Enterprise is the next phase."
[Next →]

**Step 9 — Test Suite + Run It Yourself**
> "497 tests. Feature leakage detection, security guardrails, model rollback drill,
> replay simulation, Arena gate coverage, EDI ingest end-to-end."
Show the one-liner: `PYTHONPATH=backend pytest backend/tests/ -v`
Link to GitHub repo.
> "Clone it. Run the tests. Everything here is real."
[End of technical tour]

---

## 8. Recording Plan

### Session 1 — Buyer Tour (record after Shepherd tour is built)
- Tool: Loom (face cam bottom-right, screen, live voiceover)
- Length: ~12–15 minutes full walkthrough
- Talking points: one bullet per Shepherd step (speak naturally, not verbatim)
- GIF cuts needed from this recording:
  - Stockout alert card appearing (30s)
  - SHAP waterfall loading after click (20s)
  - System Events panel lighting up after Disapprove (45s)
  - ROI card final view (20s)

### Session 2 — Technical Tour (record after all backend features built)
- Tool: Loom (same setup)
- Length: ~18–22 minutes
- GIF cuts needed:
  - Arena gate-by-gate reveal animation (60s)
  - System Events panel with technical labels (45s)
  - Two SKUs side by side with different SHAP stories (45s)
- Terminal sections: Asciinema for pytest run output (hiring managers can pause/copy)

### Splash Page Embeds
- 4–6 GIF clips from the recordings above
- Autoplay, no sound, looped
- Each under 60 seconds, one concept per clip

---

## 9. Build Order — Prioritized

Each item: `/spec` first → implement + tests → `/test-loop` until green → commit.

### Foundation (build first — everything depends on this)
- [x] **Demo dataset**: `data/demo/` + `seed_demo.py` — Summit Outdoor Supply, Day 95 state
  with active shadow challenger engineered in (WS-1.1, WS-1.2)

### Backend P0 (model must be good before demo is recorded)
- [x] **LightGBM switch** — zero LSTM weight; pure LightGBM pipeline (WS-2.1)
- [x] **WAPE + MASE metrics** — replaced MAPE; training pipeline updated (WS-2.2)
- [ ] **Pre-trained model** — train on full Favorita + M5; cold-start on 27 rows is not demoable
- [x] **Timezone-aware feature engineering** — all temporal features now tz-correct (WS-2.4)
- [x] **SHAP endpoint** — `GET /forecasts/{id}/explain`; Redis cache; tenant isolation (WS-3, WS-7.1)
- [x] **Retrain orphan cleanup** — `status = failed` on error; prevents silent retrain blocks (WS-2.6)
- [x] **Redis retrain lock** — concurrent retrains guarded with Redis distributed lock (WS-2.5)
- [x] **Model quality CI test** — `test_model_quality_ci.py`; MASE < 1.0 gate (WS-2.7)

### Frontend P0 (what the demo shows)
- [x] **Platform Activity Feed** — `ActivityFeed.tsx`; 95-day Summit arc; mounted on DashboardPage
- [x] **System Events Panel** — `SystemEventsPanel.tsx`; live WS feed; auto-expands on `?tour=technical`;
  mounted on DashboardPage; sets `window.__demoEventReceived` for Shepherd interop
- [x] **SHAP waterfall UI** — `SHAPWaterfall.tsx`; horizontal Recharts bars; plain-language labels;
  lazy-fetches on expand; wired into ForecastsPage top movers
- [x] **Model improvement timeline** — `ModelTimeline.tsx`; MASE sparkline Day 1→95; champion/challenger
  annotations; mounted on DashboardPage
- [x] **Graduation notification** — `GraduationToast.tsx`; Radix UI Toast; built, not yet wired to WS event
- [x] **Data freshness banner** — `DataFreshnessBanner.tsx`; shows when `hoursSinceSync > 48`; built,
  not yet mounted (no active stale-data scenario in demo)
- [x] **Welcome modal** — `WelcomeModal.tsx`; sessionStorage flag; mounted in `ModernDashboardLayout`
- [x] **Mode switching** — `useDemoMode.ts` hook; `?tour=buyer|technical`; wired into SystemEventsPanel
  and SHAPWaterfall; DashboardPage and ForecastsPage use it

### Shepherd.js Tours
- [ ] **Shepherd.js installed** — `npm install shepherd.js`
- [ ] **Buyer tour** — 8 steps per §6; `advanceOn` wired to disapprove click
- [ ] **Technical tour** — 9 steps per §7; Arena gate panel; GitHub links
- [ ] **Reactive step dependency** — System Events panel WebSocket must be live before
  Shepherd step 6/7 can work; build panel first, tour second

### Splash Page
- [ ] **`/welcome` route** — single page; two CTA buttons; GIF embeds (add after recording)

### API Test Coverage (32 untested endpoints from BRAINSTORM §23)
- [ ] `test_reports_api.py` — stockout-risk, inventory-health, forecast-accuracy (P1 for demo)
- [x] `test_outcomes_api.py` — ROI endpoint tests: unit + schema + HTTP integration layers
- [ ] `test_forecasts_explain_api.py` — SHAP endpoint (P1 — used in both tours)
- [ ] Remaining 25 endpoints — P2, before first customer

---

## 10. Shepherd.js Reactive Steps — Implementation Note

The key technical challenge: Shepherd step 6 (System Events panel lights up) must
fire AFTER the WebSocket event arrives from the Disapprove click — not immediately
when the click happens.

Implementation pattern:
```typescript
// Step 5: advance on disapprove click
{
  id: 'disapprove-cta',
  advanceOn: { selector: '#po-disapprove-btn', event: 'click' }
}

// Step 6: wait for WebSocket event before showing tooltip
{
  id: 'system-events-reveal',
  beforeShowPromise: () => new Promise(resolve => {
    // WebSocket handler sets a flag when feedback_loop event arrives
    const check = setInterval(() => {
      if (window.__demoEventReceived) {
        clearInterval(check);
        resolve();
      }
    }, 100);
  }),
  text: 'Your decision just triggered three automatic processes...',
  attachTo: { element: '#system-events-panel', on: 'left' }
}
```

The WebSocket event handler sets `window.__demoEventReceived = true` when the
feedback_loop event arrives. Shepherd polls for the flag before showing step 6.
This makes the step feel genuinely reactive — the tooltip appears because something
real just happened, not because the user clicked Next.

---

## 11. Enterprise Positioning Summary

| Component | Status | Demo treatment |
|---|---|---|
| Multi-tenant RLS | Production-ready | Shown in technical tour step 7 (test proof) |
| EDI X12 (846/856/810) | Production-ready | Mentioned in technical tour step 8 |
| Celery horizontal scaling | Architected | Mentioned in technical tour step 8 |
| Pandera 3-gate validation | Production-ready | Mentioned in technical tour step 8 |
| Per-tenant MLflow namespacing | Partial | Honest "partial" in technical tour |
| Native ERP connectors | Roadmap | Honest roadmap in technical tour |
| HA Celery scheduler | Roadmap | Honest roadmap in technical tour |
| Staging environment | Roadmap | Honest roadmap in technical tour |

---

## 12. Session Handoff State

When a new session picks up this plan:

1. Read this file
2. Read `docs/BRAINSTORM.md §19` for full P0/P1 context
3. Run the test suite: `PYTHONPATH=backend pytest backend/tests/ -v --tb=short 2>&1 | tail -20`
4. Check the build order in §9 — find the first unchecked item
5. Run `/spec` before touching any code
6. Run `/test-loop` after implementation until green
7. Commit each item separately, push to `claude/analyze-codebase-FEu8K`
8. Check the item off in §9

**Current state (February 2026)**:

Backend P0: **7/8 done**. Only remaining item is pre-trained model (cold-start still on 27 rows).

Frontend P0: **8/8 done** (all components built and mounted). Two edge-case items not actively
wired: `GraduationToast` (needs WS graduation event trigger) and `DataFreshnessBanner` (no stale
data scenario in demo; only relevant if sync gap > 48h).

Demo flow end-to-end functional:
- `/ → WelcomeModal → ?tour=buyer|technical`
- DashboardPage: KPIs + ModelTimeline + ActivityFeed + SystemEventsPanel
- ForecastsPage: top movers with inline SHAPWaterfall per product

**Next**: Shepherd.js tours (§9 — Shepherd.js Tours). Start with `npm install shepherd.js`,
then buyer tour (8 steps), then technical tour (9 steps). Buyer tour first — shorter and simpler,
establishes the `advanceOn` + `beforeShowPromise` pattern needed for both.
