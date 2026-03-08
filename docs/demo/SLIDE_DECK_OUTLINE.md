# Slide Deck Outline (12-15 Slides, Non-Technical + Technical Balanced)

## 1. Title
- ShelfOps: Inventory Intelligence for SMB Retail
- Subtitle: HITL decisions + auditable ML operations
- Name, role target, date

## 2. Why This Exists
- Stockout/overstock/ghost inventory in day-to-day retail operations
- 4-year retail operations perspective: where manual checks fail

## 3. Business Impact Framing
- What is lost today: margin leakage, labor waste, missed sales
- How ShelfOps reduces preventable decision errors
- Use formula framing (not inflated claims): potential savings = avoided stockout loss + reduced overstock markdowns

## 4. Product Scope (Live Today)
- Dashboard, alerts, inventory, forecasts, integrations
- Mid-market-first design for lean teams

## 5. Who Uses ShelfOps
- Store managers: guided buy decisions, fewer manual guesses
- Corporate ops: cross-store visibility and auditability
- DS/ML teams: reproducible experimentation and promotion controls

## 6. Workflow in Plain English
- "System suggests -> human decides -> decision is logged -> model learns over time"
- Keep this slide visual and non-technical

## 7. System Architecture (Technical)
- API + Postgres + Redis + workers + MLflow
- Queue split (`sync` vs `ml`) and why it matters for reliability

## 8. HITL + Governance Proof
- PO approve/edit/reject workflow
- Decision history and audit persistence (`po_decisions`)
- Experiment approval/completion flow

## 9. MLOps Control Loop
- Scheduled sync, alert checks, drift checks, retrain cadence
- Model health endpoint + manual trigger capability

## 10. DS Iteration Workflow
- Fast subset exploration -> reproducible run logs -> baseline comparison
- XGBoost-first runtime, optional LSTM ensemble
- Hypothesis example slide with adopt/reject gate

## 11. Current Results and Boundaries
- Current metrics from `backend/models/registry.json` and `backend/reports/iteration_runs.jsonl`
- Explicit limitation: seeded/simulated data, tenant onboarding next

## 12. Today vs Roadmap
- Today: mid-market operational demo ready
- In hardening: enterprise parser/runtime gates and broader SLA-level validation

## 13. Demo Flow Map
- 15-minute sequence: slides -> frontend -> API/log proof -> close
- What is shown live vs discussed as roadmap

## 14. Hiring Fit + Commercial Fit
- Hiring: end-to-end ownership across data, ML, APIs, ops
- SMB: practical pilot-ready workflows
- Enterprise: architecture-aligned, hardening in progress

## 15. Close
- Summary: practical product + technical depth + governance discipline
- CTA options: interview loop, pilot discussion, technical deep-dive
