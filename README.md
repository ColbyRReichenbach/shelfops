<div align="center">

# ShelfOps
**Inventory intelligence for SMB retail: forecast-guided replenishment, human-reviewed purchase-order workflows, and auditable ML operations.**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2-FDB515?logo=timescale&logoColor=black)](https://www.timescale.com/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking-0194E2?logo=mlflow&logoColor=white)](https://mlflow.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![pytest](https://img.shields.io/badge/pytest-tested-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

Built by **Colby Reichenbach**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/colby-reichenbach/)
[![Portfolio](https://img.shields.io/badge/Portfolio-Check%20Out%20My%20Work-4B9CD3?style=flat-square&logo=githubpages&logoColor=white)](https://colbyrreichenbach.github.io/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/ColbyRReichenbach)

</div>

---

## Why I Built It

I spent four years working in retail, most of it in inventory and receiving. The same problems showed up at every store I worked, regardless of size or category:

- **Ghost stock** — the system says you have 12 units. The shelf is empty. Nobody knows where they went, and nobody has time to find out.
- **Backroom deadstock** — merchandise sitting on a pallet for three weeks because it never got properly scanned, counted, or moved to the floor.
- **Ordering by gut** — managers placing purchase orders based on memory and habit, not data. Fast-movers stock out on Friday. Slow-movers pile up and get marked down at end of quarter.
- **No early warning** — by the time you realize something's wrong, customers have already walked out empty-handed.

ShelfOps is my attempt to turn that operational pain into a usable system: a product for SMB retailers built with the backend and MLOps discipline I would expect in a much larger platform.

---

## What It Does

ShelfOps combines inventory visibility, forecast-guided replenishment, alert triage, and human-reviewed purchase-order decisions in one workflow.

- **Forecast-guided buying** with a LightGBM-first demand model and business-rule overlays
- **Human-in-the-loop PO workflow** with approve, edit, reject, and decision-history paths
- **Alert and anomaly review** so unusual inventory or demand behavior is surfaced in the same operator workflow
- **Auditable ML lifecycle** with champion/challenger tracking, retraining logs, and promotion gates
- **Multi-tenant backend patterns** for store, org, and integration boundaries

---

## Built For

SMB retailers that still rely on spreadsheets, manual checks, or fragmented tooling, but want stronger inventory discipline without enterprise rollout complexity.

The platform also includes EDI, SFTP, and Kafka-style ingestion paths to demonstrate how the same workflow can scale into more enterprise-shaped environments. Those enterprise paths are architecture proof, not a claim of broad enterprise GA readiness.

---

## Demo

Runbook and demo assets live in [`docs/demo/`](./docs/demo).

---

## Docs

- [Technical README](./TECHNICAL.md) — architecture, ML design, how to run locally, CI/CD
- [Engineering docs](./docs) — API contracts, model readiness, operations runbooks
- [Future Integrations](./docs/product/future_integrations.md) — platform vision: weather intelligence, social trend signals, enterprise cloud scale
- [Known Limitations](./docs/product/known_limitations.md) — current architectural boundaries and design tradeoffs

---
