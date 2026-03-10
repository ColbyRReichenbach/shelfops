# ShelfOps Demo Audience Playbook

## Purpose
Use this playbook to adapt the same ShelfOps demo for different audiences without changing the core truth of the product.

Primary scripts:
- `docs/demo/BUSINESS_WALKTHROUGH.md`
- `docs/demo/TECHNICAL_WALKTHROUGH.md`

Core framing:
- **Product for SMB:** built for smaller retailers still making inventory decisions manually or in spreadsheets.
- **Project for enterprise:** implemented with multi-tenant security, worker orchestration, auditable MLOps, and enterprise-style adapters to show scale and production thinking.

Role model for the presentation:
- act like a technical product manager who also built the system
- explain the business problem, then the product workflow, then the architecture and operating model behind it
- always tie technical depth back to user trust, operator behavior, and business outcomes

## The One Sentence Positioning
"ShelfOps is intelligent inventory infrastructure for SMB retailers, built with enterprise-grade backend and MLOps patterns so smaller operators can access workflows that usually require much larger systems and teams."

## Non-Negotiable Proof Points
Every version of the demo should prove these:

1. Retail domain knowledge is real.
- You spent 4+ years in retail operations.
- The problem framing should mention stockouts, ghost inventory, dead stock, receiving errors, buyer overrides, and why manual replenishment fails.

2. The product is operational, not just analytical.
- Forecasts connect to purchase-order decisions.
- Humans can approve, edit, or reject recommendations.
- Those decisions are persisted and later reused as feedback signals.

3. The backend is production-minded.
- Multi-tenant security is enforced at the DB layer with tenant-scoped sessions and RLS patterns.
- Workloads are separated into queues and scheduled workers.
- Integrations, forecasts, retrains, and alerts are auditable.

4. AI is integrated thoughtfully.
- AI/ML is used where it reduces operational ambiguity: forecasting, drift detection, explainability, and experiment governance.
- High-impact business decisions stay human-controlled.

5. The enterprise layer is architecture proof, not a commercial overclaim.
- EDI, SFTP, and Kafka/event-stream paths demonstrate integration breadth and backend depth.
- Enterprise onboarding is still non-GA.

6. Different internal users need different surfaces.
- Executives or general stakeholders start on the dashboard.
- Operators live more in alerts, inventory, and forecasts.
- Technical owners use operations and ML Ops.
- The product is intentionally designed for the internal team, not one generic user.

## Audience Priority Matrix

### Hiring Manager: Junior / Mid MLOps
Lead with:
- queue-separated workers
- retrain/forecast/monitor lifecycle
- model registry and promotion gates
- reliability, validation, and observability discipline

Recommended script:
- `TECHNICAL_WALKTHROUGH.md`

What they need to believe:
- you can reason about production ML systems, not just notebooks
- you understand deployment boundaries, failure modes, and repeatability
- you can explain why the architecture choices were practical, not just technically interesting

### Hiring Manager: Data Scientist / Applied ML
Lead with:
- why the problem matters operationally
- feature engineering and forecast-to-decision loop
- model choice reasoning
- experiment governance and measurable iteration

Recommended script:
- start with `BUSINESS_WALKTHROUGH.md`, then transition into `TECHNICAL_WALKTHROUGH.md`

What they need to believe:
- you can connect model quality to business outcomes
- you do not overfit the story to vanity metrics
- you understand hypothesis tracking, business-safe promotion, and why model iteration is an operating process

### Hiring Manager: Data / Analytics Engineer
Lead with:
- data contracts
- ingestion pathways
- canonicalization
- observability and reproducible artifacts

Recommended script:
- `TECHNICAL_WALKTHROUGH.md`

What they need to believe:
- you can build trustworthy pipelines and expose usable operational data
- you understand canonicalization, async boundaries, and audit trails

### SMB Owner / Pilot Conversation
Lead with:
- fewer manual inventory decisions
- better reorder timing
- visibility across stores/products
- human override still available

Recommended script:
- `BUSINESS_WALKTHROUGH.md`

What they need to believe:
- this reduces chaos without replacing their judgment
- onboarding can start with existing exports and limited technical maturity
- different people on their team would actually know where to work inside the product

## Critical Topics To Hit Live
- Why you built it from direct retail pain instead of a generic AI prompt.
- Why the architecture is “big” for an SMB product: stronger systems let the customer workflow stay simple.
- Why human-in-the-loop is intentional: automate detection and recommendation, not silent purchasing.
- Why LightGBM is the current operating model: practical, strong on tabular demand data, and appropriate for current data scale.
- Why business logic exists on top of ML: this product supports decisions, not just predictions.
- Why forecasting and anomaly detection are separate model problems serving different operational purposes.
- Why experiments, shadow comparison, archive, and rollback are part of trust, not just MLOps decoration.

## Positioning Boundary
- Lead with SMB workflows that are fully demoable today.
- Present enterprise support as implemented architecture under active hardening.
- Reuse this close:
  - `Today`: truthful live workflow for hiring-manager walkthroughs.
  - `Pilot next`: operator visibility, integration resilience, and release confidence for a Square/CSV-first SMB rollout.
  - `Later`: broader enterprise hardening and richer model sophistication.

## Phrases Worth Reusing
- "Project for enterprise, product for SMB."
- "Automate detection and recommendation; keep high-impact decisions human-controlled."
- "This is not black-box automation. It is auditable decision support."
- "The architecture is scaled up so the customer workflow can stay simple."
- "I built the backend as seriously as the model, because trust in operations comes from system behavior, not just forecast accuracy."

## What To Avoid
- Do not claim enterprise GA readiness.
- Do not lead with raw ML metrics before showing the operational workflow.
- Do not imply real-time streaming if the behavior is scheduled polling/consumption.
- Do not overstate model maturity; be explicit that further tenant-specific iteration is still needed.
- Do not describe the ML Ops page as if it is for all users in a company.
