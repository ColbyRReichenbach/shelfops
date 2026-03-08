<div align="center">

# ShelfOps
**AI-powered inventory intelligence for retail — predicts stockouts 2–3 days early, optimizes reorder points, and automates PO workflows. Multi-tenant SaaS with production ML governance.**

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
[![pytest](https://img.shields.io/badge/pytest-497%20passing-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)

Built by **Colby Reichenbach**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/colby-reichenbach/)
[![Portfolio](https://img.shields.io/badge/Portfolio-Check%20Out%20My%20Work-4B9CD3?style=flat-square&logo=githubpages&logoColor=white)](https://colbyrreichenbach.github.io/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/ColbyRReichenbach)

</div>

---

## The Problem I Kept Seeing

I spent four years working in retail, most of it in inventory and receiving. The same problems showed up at every store I worked, regardless of size or category:

- **Ghost stock** — the system says you have 12 units. The shelf is empty. Nobody knows where they went, and nobody has time to find out.
- **Backroom deadstock** — merchandise sitting on a pallet for three weeks because it never got properly scanned, counted, or moved to the floor.
- **Ordering by gut** — managers placing purchase orders based on memory and habit, not data. Fast-movers stock out on Friday. Slow-movers pile up and get marked down at end of quarter.
- **No early warning** — by the time you realize something's wrong, customers have already walked out empty-handed.

These aren't edge cases. They're the daily reality for thousands of independent and mid-size retailers, and they quietly eat margins every single day. I built ShelfOps because I wanted to give those stores the same kind of inventory intelligence that enterprise retailers pay millions for — without the enterprise price tag or a six-month implementation.

---

## What ShelfOps Does

ShelfOps connects to your point-of-sale and ERP data, learns your demand patterns, and gives you a **2–3 day early warning** before a stockout hits. Then it acts — generating reorder recommendations, drafting purchase orders, and flagging anomalies before they turn into lost sales.

- **Predicts stockouts 2–3 days early** using a machine learning ensemble trained on your store's own history
- **Dynamic reorder optimization** — calculates reorder points and order quantities that adjust as patterns change, not static thresholds you set and forget
- **Automated PO workflows** — drafts and routes purchase orders without manual spreadsheet work
- **Ghost stock detection** — surfaces inventory discrepancies between what the system thinks you have and what's actually there
- **Promotion-aware forecasting** — accounts for markdowns and campaigns so demand spikes don't throw off your baseline
- **Multi-location ready** — built from day one to manage multiple stores under one account

---

## Built For

Small and mid-size retailers who need enterprise-grade inventory intelligence without the enterprise complexity. The integration layer supports EDI (X12 846/856/810), SFTP batch files, and event-stream integrations (Kafka/Redpanda via scheduled consumers), so the platform scales with you as your operation grows.

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
