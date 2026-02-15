# The Data Scientist Role at ShelfOps

> **Document status**: Strategy narrative. Any percentages/threshold examples here are illustrative unless separately validated in `docs/RELEASE_READINESS.md` or code-backed tests.

> **Position Strategy**: At ShelfOps, the Data Scientist is not a back-office model maintainer. You are a **Strategic Intelligence Lead**. The "Glass Box" architecture of ShelfOps is designed to empower you to translate model outputs into executive business decisions.

---

## 1. Core Philosophy: "Glass Box" Operations

Traditional retail AI is a "Black Box"—it spits out an order number, and no one knows why. ShelfOps is different.

*   **You don't just predict demand.** You explain *why* demand is changing (using SHAP values).
*   **You don't just optimize inventory.** You arbitrate between capital efficiency (low inventory) and revenue capture (high availability).
*   **You don't just monitor errors.** You investigate human overrides to capture tribal knowledge.

---

## 2. Key Workflows (The "Day-to-Day")

### A. The "Cold Start" Transition Strategy
**Challenge**: New products have no history. Standard models fail here.
**Your Role**:
1.  **Monitor the Tier**: Watch the `backend/ml/features.py` logic. Ensure products are correctly tagged as `cold_start`.
2.  **Validate Graduation**: A product shouldn't move to `production` tier just because it has 30 days of data. It should move only when the *Production Model* consistently beats the *Cold Start Baseline*.
3.  **Action**: You act as the gatekeeper for this transition, preventing volatile forecasts from wrecking auto-replenishment.

### B. Champion/Challenger Arena
**Challenge**: Retail dynamics change (e.g., new competitor, inflation, viral trends). Static models rot.
**Your Role**:
1.  **Hypothesis Generation**: "I suspect 'Days Since Last Promo' is a key driver for our beauty category."
2.  **Experimentation**: Train a Challenger XGBoost model with this new feature in the `ml-worker` container.
3.  **The "Arena"**: Register it as `v2.1-candidate`. The system unknowingly runs it in "Shadow Mode" against the Champion (`v2.0`).
4.  **Promotion**: If the Challenger reduces MAE by >5% over 2 weeks, *you* authorize the promotion to Champion.

### C. Forensic Analysis of "Human Overrides" (HITL)
**Challenge**: Store managers often know things the AI doesn't (e.g., "The road outside is under construction").
**Your Role**:
1.  **Signal Detection**: Query the `actions` database for `action_type = 'ordered'` where the quantity differs from the AI suggestion by >20%.
2.  **Root Cause Analysis**:
    *   *Scenario A (Theft)*: Manager ordered more because inventory count was wrong (phantom inventory). -> **Fix**: Trigger cycle count.
    *   *Scenario B (Local Event)*: Manager ordered more because of a local festival. -> **Fix**: Add a "Local Event Calendar" feature to the model.
3.  **Feedback Loop**: You turn these "errors" into new features.

### D. Anomaly Triage & Investigation
**Challenge**: The `IsolationForest` model acts as a smoke detector. It rings often.
**Your Role**:
1.  **Filter Noise**: Tune the contamination parameter to balance precision/recall.
2.  **Investigate Criticals**: When an `inventory_discrepancy` alert fires:
    *   Check the SHAP plots.
    *   If Sales > 0 but Inventory is flat, it's an integration failure.
    *   If Inventory > 0 but Sales = 0 for 7 days, it's "Ghost Inventory" (item is lost in the backroom).
3.  **Business Impact**: You directly save the company money by surfacing these "Ghost Items" for immediate markdown or retrieval.

---

## 3. Strategic Metrics to Own

You are judged not just on Model Accuracy, but on **Financial Performance**.

### 1. GMROI (Gross Margin Return on Investment)
*   **Formula**: $\frac{\text{Gross Margin}}{\text{Average Inventory Cost}}$
*   **Target**: > 3.0 (For every $1 invested in inventory, get $3 back in margin).
*   **Your Lever**: Tighten the `safety_stock` logic in `backend/ml/inventory.py`. Reducing excess safety stock denominator increases GMROI directly.

### 2. Stockout Avoidance vs. Holding Cost
*   **The Trade-off**: Zero stockouts expensive (requires massive inventory).
*   **Your Lever**: Adjust the `service_level` parameter (default 0.95) based on SKU velocity (ABC Analysis).
    *   *A-Items (High Vol)*: 98% Service Level.
    *   *C-Items (Low Vol)*: 90% Service Level.

### 3. Forecast Value Added (FVA)
*   **Definition**: How much better is *your* model than a naive "Same as Last Year" baseline?
*   **Target**: Positive FVA across all categories. Negative FVA means the complex model is worse than guessing—kill it.

---

## 4. The Toolkit

*   **Experiment Tracking**: MLflow (http://localhost:5000)
    *   *Log every hypothesis.*
*   **Explainability**: SHAP (Shapley Additive Explanations)
    *   *Never say "The model said so." Show the breakdown.*
*   **Data Validation**: Pandera
    *   *Garbage In, Garbage Out protection.*
*   **Database**: TimescaleDB (SQL)
    *   *Your source of truth for time-series analysis.*
