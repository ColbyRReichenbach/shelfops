# ShelfOps Full Demo Script

This file is now the master reference, not the primary script you should present from.

## Use These Instead
- [BUSINESS_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/BUSINESS_WALKTHROUGH.md): recruiters, SMB owners, pilot conversations, general hiring-manager screens
- [TECHNICAL_WALKTHROUGH.md](/Users/colbyreichenbach/Downloads/shelfops_project/docs/demo/TECHNICAL_WALKTHROUGH.md): ML/MLOps/engineering interviewers and technical deep dives

## Why The Split Exists
One blended demo forces you to change altitude too early.

The better structure is:
1. Start with the business walkthrough to hook attention with the real retail problem, your domain knowledge, and the platform workflow.
2. Switch to the technical walkthrough only when the audience wants to understand architecture, ML systems, MLOps, and tradeoffs in depth.

## Shared Positioning Anchor
Use this in either version:

> ShelfOps is an inventory intelligence platform for smaller retailers that still operate manually or with fragmented tooling. It helps them move from gut-feel replenishment to auditable, data-backed decisions.

Then add:

> The short version is: product for SMB, project for enterprise.

## Shared Non-Negotiable Proof Points
Every version should still prove these:
1. Retail domain knowledge is real.
2. The product is an operational workflow, not just a model.
3. AI is integrated thoughtfully with business logic and human review.
4. The backend is production-minded.
5. Enterprise-scale patterns exist to prove technical depth, not to overclaim readiness.

## Shared Runtime Commands
Prepare deterministic demo state first:

```bash
PYTHONPATH=backend python3 backend/scripts/prepare_demo_runtime.py
```

Optional terminal proof:

```bash
PYTHONPATH=backend python3 backend/scripts/run_demo_terminal_showcase.py
```

Bring up local stack if needed:

```bash
export MLFLOW_HOST_PORT=5001
docker compose up -d db redis mlflow redpanda api ml-worker sync-worker celery-beat
curl -s http://localhost:8000/health
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```
