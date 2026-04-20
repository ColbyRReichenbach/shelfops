# ShelfOps Pre-Pilot Checklist

Use this checklist before outreach, live walkthroughs, or a first pilot kickoff. The goal is not to make ShelfOps look finished. The goal is to make the product feel credible, reliable, and low-friction to try.

## 1. Runtime Readiness

- `docker compose up -d db redis redpanda api` succeeds without manual port workarounds.
- `./scripts/setup_production.sh` finishes cleanly.
- `./scripts/bootstrap_sample_merchant.sh` loads the canonical walkthrough tenant without ad hoc SQL or notebooks.
- `cd frontend && npm run dev` renders the app without console-breaking API errors.

## 2. Canonical Walkthrough State

- Data Readiness shows a real onboarding state, not an empty shell.
- Replenishment shows a meaningful queue with risk and interval context.
- Impact shows recent recommendation activity plus scenario comparison.
- Operations shows alerts, sync freshness, and model runtime health.
- Model Performance shows an active champion, recent backtests, and forecast quality summaries.

## 3. Onboarding Story

Every pilot conversation should answer:

- What data do you need from us?
- How long does onboarding take?
- What happens after the files or POS connection are provided?
- What does the buyer actually do inside the product?

Current supported answers:

- onboarding paths: CSV and Square
- minimum data: stores, products, sales history, inventory snapshots
- first working loop: Data Readiness -> Replenishment -> Impact -> Operations

## 4. Evidence Story

Before outreach, keep the public story simple:

- benchmark-backed forecast foundation on M5
- stockout-aware methodology track on FreshRetailNet
- human-reviewed replenishment workflow
- labeled measured, estimated, provisional, and simulated outputs

Do not expand the benchmark list unless there is a specific gap that matters for a pilot conversation.

## 5. Model Readiness

The current model is good enough for pre-pilot positioning if:

- the active champion remains benchmark-backed and internally consistent
- forecast ranges and segment quality are visible in Model Performance
- the product stays honest about what is measured versus modeled

Pre-pilot model work should focus on:

- stronger presentation of current evidence
- merchant onboarding readiness
- learning plan for the first real merchant

Pre-pilot model work should not focus on:

- adding more public datasets without a clear reason
- architecture churn for its own sake
- benchmark breadth over onboarding quality

## 6. First Merchant Success Criteria

Before the first real pilot starts, be clear on what success means:

- onboarding completed without heroic manual cleanup
- recommendations reviewed with accept, edit, or reject decisions
- buyer feedback captured with reason codes
- forecast quality and decision outcomes reviewable week by week
- a case-study-ready summary can be produced at the end of the pilot

## 7. Local Walkthrough Flow

Use this when you need a clean walkthrough-ready tenant:

```bash
docker compose up -d db redis redpanda api
./scripts/setup_production.sh
./scripts/bootstrap_sample_merchant.sh
cd frontend && npm run dev
```

That path should stay stable. If it drifts, fix the product flow instead of creating a second demo app.
