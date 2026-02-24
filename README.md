# ShelfOps

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2-FDB515?style=flat-square&logo=timescale&logoColor=black)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)

> AI-powered inventory intelligence — built from 4 years on the retail floor.

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

Small and mid-size retailers who need enterprise-grade inventory intelligence without the enterprise complexity. The integration layer supports EDI (X12 846/856/810), SFTP batch files, and real-time event streams (Kafka/Redpanda), so the platform scales with you as your operation grows.

---

## Demo

> Screenshots and live demo coming soon.

---

## Docs

- [Technical README](./TECHNICAL.md) — architecture, ML design, how to run locally, CI/CD
- [Engineering docs](./docs) — API contracts, model readiness, operations runbooks

---

## About

Built by **Colby Reichenbach**

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/colby-reichenbach/)
[![Portfolio](https://img.shields.io/badge/Portfolio-Visit-000000?style=flat-square&logo=githubpages&logoColor=white)](https://colbyrreichenbach.github.io/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/ColbyRReichenbach)
