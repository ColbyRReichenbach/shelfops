# 10-Minute Video Script (Hiring + SMB Narrative)

## 0:00-0:50 — Opening Positioning
Say:
"ShelfOps is retail inventory intelligence for teams that do not have enterprise-scale tooling. It combines forecasts, alerts, and human approvals so decisions are both smarter and auditable."

Show:
- Title slide with one-sentence value proposition.

## 0:50-2:00 — Problem + Personal Credibility
Say:
"After four years in retail inventory operations, I saw the same issue repeatedly: visual checks and gut-based ordering lead to stockouts, overstock, and ghost inventory. ShelfOps was built to replace that with measurable workflows."

Show:
- Problem slide: stockout vs overstock + ghost inventory definitions.

## 2:00-4:30 — Product Flow (Frontend)
Say and show:
1. Dashboard: "What requires attention now."
2. Alerts: "How teams triage and close issues."
3. Inventory: "Store/SKU-level posture and action context."
4. Forecasts: "Predicted demand to guide buying."
5. Integrations: "Square works now; broader connectors are staged."

## 4:30-6:30 — Human-in-the-Loop Decisions (API Evidence)
Say:
"ShelfOps suggests orders, but humans approve, edit, or reject. Every decision is logged."

Show:
- Suggested PO list.
- Approve one with quantity edit.
- Reject one with reason code.
- Decision history endpoint for the same PO IDs.

## 6:30-7:45 — MLOps Controls (API + Logs)
Say:
"Model operations are observable: health checks, drift checks, and governed experiments."

Show:
- `/models/health`
- Trigger one monitoring task and show worker logs
- `/experiments` and `/ml-alerts` endpoints

## 7:45-8:45 — DS/ML Iteration Evidence
Say:
"Model iteration is reproducible: each run stores parameters, metrics, and notes."

Show:
- `backend/reports/iteration_runs.jsonl`
- `backend/models/registry.json`
- `backend/models/champion.json`
- `backend/reports/iteration_notes/`

## 8:45-9:30 — Data Limitations + Customer Onboarding Plan
Say:
"Current results are based on seeded/simulated data for reproducibility. The onboarding path is to map customer POS/inventory schemas, validate contracts, run shadow mode, and then promote per-tenant models using approval gates."

Show:
- One slide with "Today vs Next" path.

## 9:30-10:00 — Close
Say:
"Today is a truthful live workflow: alerts, forecasts, purchase-order decisions, and governed model operations. Pilot next is observability, integration resilience, and release confidence for a first SMB rollout. Later is broader enterprise hardening and deeper model sophistication, but I do not overclaim that those pieces are fully ready today."
