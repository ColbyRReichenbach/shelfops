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
- SMB-first design for lean teams
- "Project for enterprise, product for SMB" framing

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
- Multi-tenant security and tenant-isolated backend behavior
- Why the architecture is intentionally stronger than the SMB workflow looks

## 8. HITL + Governance Proof
- PO approve/edit/reject workflow
- Decision history and audit persistence (`po_decisions`)
- Experiment approval/completion flow

## 9. MLOps Control Loop
- Scheduled sync, alert checks, drift checks, retrain cadence
- Model health endpoint + manual trigger capability
- Why automation is bounded by business risk

## 10. DS Iteration Workflow
- Fast subset exploration -> reproducible run logs -> baseline comparison
- LightGBM-first runtime, legacy compatibility for older artifacts
- Hypothesis example slide with adopt/reject gate

## 11. Model + Business Logic Choices
- Why LightGBM is the current operating model
- Why business rules still exist on top of ML
- Why human override remains part of the system

## 12. Current Results and Boundaries
- Current metrics from `backend/models/registry.json` and `backend/reports/iteration_runs.jsonl`
- Explicit limitation: seeded/simulated data, tenant onboarding next

## 13. Today vs Roadmap
- Today: mid-market operational demo ready
- In hardening: enterprise parser/runtime gates and broader SLA-level validation

## 14. Demo Flow Map
- 15-minute sequence: slides -> frontend -> API/log proof -> close
- What is shown live vs discussed as roadmap

## 15. Hiring Fit + Commercial Fit
- Hiring: end-to-end ownership across data, ML, APIs, ops
- SMB: practical pilot-ready workflows
- Enterprise: architecture-aligned, hardening in progress
