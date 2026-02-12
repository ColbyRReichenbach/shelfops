# Commercial Product Audit: The Path to Enterprise Readiness

> **Status**: 🟢 **Concept Proven** | 🟡 **Engineering Foundation** | 🔴 **Operational Product**
>
> **Executive Summary**: ShelfOps currently demonstrates *technical capability* (it can predict) but lacks *commercial utility* (it cannot execute). To become a viable product that a retailer would buy, it must transition from a "Forecasting Tool" to an "Inventory Operating System." This requires bridging the gap between Prediction (ML) and Action (Operations).

---

## 1. MLOps Maturity ( The "Brain" )

**Current State**: Manual retraining, static deployment.
**Commercial Standard**: Automated, continuous learning with safety rails.

| Concept | Status | Gap | Remediation |
| :--- | :--- | :--- | :--- |
| **Model Retraining** | 🟡 Partial | `retrain.py` exists but runs on ad-hoc CELERY trigger, not event-driven. | Implement **Airflow/Prefect** DAGs for scheduled retraining based on data arrival. |
| **Model Comparison** | 🔴 Missing | No automated way to compare Candidate vs. Champion models. | Build **The Arena**: A backtesting engine that replays last week's data on both models to calculate GMROI lift. |
| **Feature Store** | 🟡 Partial | Features calculated on-fly. No consistency between Training/Serving in real-time. | Implement a **Feature Store** (e.g. Feast or simply a robust Postgres schema) to serve consistent features. |
| **Drift Detection** | 🔴 Missing | System is blind to accuracy degradation. | Implement **EvidentlyAI** or custom drift monitoring. Alert if `Training_MAE` vs `Serving_MAE` diverges > 15%. |

---

## 2. AIOps & Observability ( The "Pulse" )

**Current State**: "Silent Failure" risk. If it breaks, nobody knows until a user complains.
**Commercial Standard**: Proactive alerting on *business* health, not just *server* health.

| Concept | Status | Gap | Remediation |
| :--- | :--- | :--- | :--- |
| **Data Freshness** | 🔴 Missing | If POS data stops arriving, model predicts 0 sales. | Implement **"Deadman Switches"**: Alert if no new transactions for Store X in 24 hours. |
| **Business Monitoring** | 🔴 Missing | No tracking of "Lost Sales" due to stockouts. | Implement **Counterfactual Logging**: "We predicted demand of 50, but stock was 0. Opportunity Cost = $500". |
| **Alert Fatigue** | 🔴 Missing | Alerts are raw. 1000 items = 1000 alerts. | Implement **Alert Grouping/Deduplication**. "Store 5 has 200 stockouts" (1 alert), not 200 alerts. |

---

## 3. Retail Context ( The "Business Logic" )

**Current State**: Generic inventory logic. Ignores the messy reality of retail.
**Commercial Standard**: Handles calendars, shrinkage, and vendor unreliability.

| Concept | Status | Gap | Remediation |
| :--- | :--- | :--- | :--- |
| **Calendars** | 🔴 Missing | Uses standard Gregorian calendar. Retailers use **4-5-4 Fiscal Calendar**. | Implement `FiscalCalendar` utility. `is_holiday` is currently hardcoded to `0` in `features.py`! |
| **Shrinkage** | 🔴 Missing | Assumes `Inventory = In - Out`. Reality: Theft/Spoilage happens. | Implement **Shrink Rate** parameter per category. Auto-adjust inventory down by X% weekly. |
| **Planograms** | 🔴 Missing | Doesn't know if a product is *supposed* to be on the shelf. | Add `Planogram` table. Don't reorder products that are "de-listed" or "seasonal out". |
| **Vendor Logic** | 🔴 Missing | Assumes fixed Lead Time. | Track **Actual vs. Promised** delivery dates. Calculate dynamic Safety Stock based on vendor variance. |

---

## 4. The "Action Gap" ( The Critical Flaw )

**Current State**: The system generates insights that go nowhere.
**Commercial Standard**: The system proactively *manages* the workflow.

### The Problem: "Static" Reorder Points
The `features.py` calculates demand, but `ReorderPoint` is a static database table.
*   **Scenario**: AI predicts a 200% surge for a promotion.
*   **Result**: System orders *nothing extra*, because `ReorderPoint` is still set to the generic low value.
*   **Fix**: Create **Inventory Optimizer**. A nightly job that updates `ReorderPoint` based on `(Forecast_Demand * Lead_Time) + Dynamic_Safety_Stock`.

### The Problem: Closed Loop
*   **Scenario**: Manager rejects a "Suggested Order".
*   **Result**: System doesn't know why. It will suggest it again tomorrow.
*   **Fix**: **Reason Codes** (`Overstock`, `Damaged`, `End of Life`). Feed this back into the model as features.

---

## 🗺️ Prioritized Roadmap for Commercialization

### Phase 1: The "Decision Engine" (High Impact)
*   [ ] **Inventory Optimizer**: Build the job to update ROP/Safety Stock dynamically.
*   [ ] **Purchase Order API**: Allow users to Approve/Reject orders.
*   [ ] **Reason Codes**: Capture *why* a human intervened.

### Phase 2: Retail Reality (Medium Impact)
*   [ ] **Holiday/Fiscal Logic**: Fix `is_holiday` in `features.py`. Integrate 4-5-4 calendar.
*   [ ] **Vendor Scorecard**: Track basic Lead Time variance.

### Phase 3: Safety Nets (Low Impact, High Trust)
*   [ ] **Drift Monitor**: Simple daily check of MAE.
*   [ ] **Data Freshness Alert**: "No data received" warning.
