# ShelfOps: Technical Architecture & MLOps Pipeline

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.14%2B-FF6F00?logo=tensorflow&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-1.7%2B-5E35B1)
![Celery](https://img.shields.io/badge/Celery-5.3%2B-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-0db7ed?logo=docker&logoColor=white)

This document details the engineering and machine learning techniques powering ShelfOps. It serves as an audit of the systems I built to transition a generic time-series concept into a resilient, retail-specific AI platform.

---

## 1. System Architecture

The application is built on a modern, decoupled microservices architecture designed to separate lightweight API traffic from heavy ML processing.

**Backend Framework:** FastAPI (Python 3.10+) for high-performance, async request handling.
**Database Layer:** PostgreSQL with TimescaleDB for localized time-series optimization. 
**Task Queue:** Celery with Redis as the broker, managing asynchronous tasks like inference, anomaly detection, and database syncing.
**Frontend Interface:** React 18, Vite, TypeScript, and TailwindCSS focusing on modular UX design.

### Container Separation
I explicitly split the Docker architecture into `api` and `ml-worker` containers. The API remains lightweight (~200MB) to horizontally scale for frontend traffic, while the heavy dependencies (TensorFlow, XGBoost, SHAP) are isolated in the ML worker container (~1.5GB) to handle scheduled training and inference jobs without blocking user interactions.

---

## 2. Advanced Machine Learning Pipeline

### Segmented Forecasting Strategy (The Fleet of Models)
Global time-series models fail in retail because high-volume groceries bury the signals of niche departments. I implemented a hierarchical **ABC Velocity Router**:
*   **"A" & "B" Items (High/Medium Velocity):** Routed to an ensemble of **XGBoost** and an **LSTM Neural Network**. 
*   **"C" Items (Slow Movers):** Routed to a dedicated **Poisson Regression** model specifically designed to handle zero-inflated demand patterns without producing noisy, fractional forecasts.

### Probabilistic Forecasting via Quantile Regression
Point forecasts (e.g., "we will sell 12 units") are dangerous for inventory management because they ignore variance. I rebuilt the loss functions for both XGBoost (using `reg:quantileerror`) and the LSTM (using a custom multi-quantile TensorFlow loss function) to output true prediction intervals: **P10, P50, and P90**.
*   This allows the system to target specific service levels (e.g., ordering to the P90 forecast for high-margin, critical items to guarantee a 90% in-stock rate).

### Feature Engineering (48 Production Features)
The system trains on 48 highly correlated features targeting retail friction, automatically scaling down to a 28-feature "Cold Start" tier for new products lacking history. Key features I engineered include:
*   `days_since_payday`: A cyclical temporal feature capturing predictable bi-weekly spending spikes.
*   `is_substitute_on_promo`: A cross-product flag to measure cannibalization and halo effects when a competitor item goes on sale.
*   `days_since_last_sale`: An exponential decay feature that acts as a proxy for "Ghost Stock" probability.

### Data Leakage & Memory Optimization
*   **Lookahead Bias Prevention:** In the LSTM pipeline, I isolated the `mean` and `std` normalization scaling strictly to the time-steps *before* the validation split point, entirely preventing the model from peeking at the future.
*   **Infinite Streaming:** Removed arbitrary pandas tail-capping and implemented `tf.keras.utils.timeseries_dataset_from_array` to generate temporal batches dynamically. This removed OOM bottlenecks, allowing the pipeline to scale indefinitely.

---

## 3. The Retail Anomaly Engine

Standard outlier detection (like Isolation Forests) throws too many false positives in retail. I built deterministic anomaly engines using real-world retail heuristics:

1. **Ghost Stock Detector (`ghost_stock.py`)**: Computes a logistic probability that a shelf is empty despite the database showing positive inventory. Triggered by high continuous projected demand against zero actual sales.
2. **Backroom Trapped Detector (`backroom_trapped.py`)**: Flags items exhibiting a sudden >80% negative trend reversal in sales while maintaining high system inventory and previous category momentum.

---

## 4. Business Logic constraint Engine

ML forecasts must be translated into actionable operations. The `alerts/engine.py` pipeline forces mathematical outputs to conform to physical supply chain reality.
*   **Case Pack & MOQ Rounding:** The engine automatically rounds the P90 Reorder Point optimizations up to the nearest Supplier Case Pack Size and Minimum Order Quantity (MOQ).
*   **Unconstrained Demand Imputation**: Before training, the system recalculates past sales to factor in out-of-stock days. Teaching a model that sales were 0 when the shelf was empty creates a downward forecasting spiral; I wrote logic to impute that lost demand first.

---

## 5. MLOps & Continuous Validation

*   **Shadow Testing (The Arena):** The system features a Champion vs. Challenger pipeline architecture. New models run in shadow-mode alongside production models to compare Mean Absolute Percentage Error (MAPE) deltas before promotion.
*   **Test Suite:** The pipeline is validated using PyTest arrays confirming exact feature counts (28/48), data leakage barriers, shape dimension mapping across the P10/P50/P90 tensors, and business-logic cap constraints.
