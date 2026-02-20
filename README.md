# ShelfOps - AI-Powered Inventory Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.14%2B-FF6F00?logo=tensorflow&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7%2B-5E35B1)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)

**Built by Colby Reichenbach** | Portfolio Project for Data Science & Machine Learning Roles

---

## Executive Summary

I built ShelfOps because, after 4 years of working on a retail store floor, I realized that the multi-billion dollar problems facing retailers aren't going to be solved by generic dashboards. Retailers lose millions to "Ghost Stock," trapped backroom merchandise, and static, reactive reorder points. 

I designed and engineered ShelfOps as an end-to-end applied AI platform. It isn't just a machine learning model sitting in a notebook; it is a full-stack, self-healing system that predicts demand, detects operational anomalies, and issues real-time alerts bound by actual physical supply chain constraints.

This project demonstrates my ability to act as a domain expert, a data engineer, an MLOps practitioner, and a full-stack developer.

## The Problem I'm Solving

Retailers lose massive amounts of revenue to stockouts despite utilizing enterprise ERP and POS systems.
*   Current systems are **reactive**, relying on static formulas (e.g., Reorder Point = Avg Daily Sales x Lead Time) that fail entirely during promotions or shifting seasonality.
*   Global systems suffer from **"Phantom Inventory"** (the computer says you have 10 units, but the shelf is empty due to theft or misplaced pallets), creating a death spiral where the system refuses to reorder an out-of-stock item.

## My Solution: ShelfOps

ShelfOps acts as an intelligence layer on top of existing data streams to execute proactive operations:

1. **Probabilistic Demand Forecasting:** Replaces static formulas with a fleet of AI models (LSTM, XGBoost, Poisson) using Quantile Regression to predict true inventory ranges (P10, P50, P90) targeting guaranteed service levels.
2. **The Anomaly Engine:** Scans real-time POS data against high-velocity forecasts to automatically detect Ghost Stock and Backroom-Trapped merchandise, prompting store associates to action.
3. **Execution Interface:** A dedicated Store Dashboard UI that hands store managers clear, actionable tasks—such as reordering inventory pre-rounded to the supplier's required Case Pack size and Minimum Order Quantities (MOQ).

---

## Features & Business Logic (Audited)

I prioritized putting the "Business" before the "Math." The models in this repository are specifically trained to handle real retail friction.

*   **Unconstrained Demand Imputation**: ML models learn that "0 sales = 0 demand". I engineered preprocessing logic to identify out-of-stock days and impute the "lost sales," preventing the model from down-casting its future forecasts.
*   **Retail Friction Feature Engineering**: The system trains on 48 highly contextual features, including `days_since_payday` (capturing bi-weekly spikes) and `days_since_last_sale` with exponential decay to map probability curves for physical stockouts.
*   **Supplier Constraints**: AI order recommendations are securely capped and rounded by actual constraints (e.g., if the model suggests 17 units but the Case Pack is 12 and the MOQ is 50, the system automatically adjusts the generated order to 60 units).

## MLOps & Architecture Overview

For a detailed deep dive into the code, models, and infrastructure, please read the [TECHNICAL_README.md](TECHNICAL_README.md).

**High-Level Stack:**
*   **Machine Learning:** TensorFlow/Keras (LSTM), XGBoost, Scikit-Learn (Isolation Forests, Poisson Regression), PyTest for validation.
*   **Backend:** Python 3.10+, FastAPI, PostgreSQL + TimescaleDB, Celery + Redis.
*   **Frontend:** React 18, TypeScript, TailwindCSS, Vite.

I built this system employing a Champion/Challenger shadow-testing arena, isolated feature normalization to prevent data leakage, and an ABC velocity router to protect low-volume items from being noisy outliers in deep learning networks.

---

## Why I Built This

I built ShelfOps to prove that I am not just someone who can tune hyperparameters. I bridge the gap between complex statistical concepts and the reality of the store floor. I understand the data because I've lived the operations, and I leverage AI as a force multiplier to architect systems that typically require a squad of specialized engineers.

I am looking for an entry-level Data Science or Machine Learning Engineer role where I can bring this level of domain expertise, engineering rigor, and execution to a world-class retail technology team.

**Ready to discuss how I can bring this thinking to your organization.**
