# ShelfOps — Future Integrations & Platform Vision

- Last updated: February 24, 2026
- Audience: builders, stakeholders, technical reviewers
- Scope: forward-looking platform investments beyond the current 8-week roadmap

These are not committed delivery items. They represent the natural growth surface of the platform once SMB launch-candidate hardening is complete and initial pilots are running.

---

## 1. Enterprise-Scale Cloud Data Infrastructure

The current stack (Postgres + TimescaleDB, Celery batch workers) serves SMB and mid-market tenants well. Scaling to enterprise retail operations — chains with hundreds of locations, millions of SKUs, and real-time POS volumes — requires a different data architecture underneath the existing product surface.

**Streaming ingestion layer**
Replace or augment the current 5-minute Celery beat polling with a persistent event-streaming tier. Apache Kafka or GCP Pub/Sub would enable true real-time POS feed processing, reducing the lag between a sale event and a forecast update from minutes to seconds. TimescaleDB continuous aggregates are already positioned to consume this.

**ERP and POS connector expansion**
The existing EDI X12, Kafka, and SFTP pathways cover a wide surface, but enterprise buyers are standardized on specific platforms. Priority connector targets: SAP S/4HANA, Oracle NetSuite, Microsoft Dynamics 365, and Shopify Plus. Each would use the existing `Integration` model and `IntegrationSyncLog` pattern — the framework is already in place.

**Data lakehouse cold tier**
Historical ML training data (>18 months) is expensive to keep in Postgres. A two-tier architecture — hot data in TimescaleDB, cold data in Snowflake or a similar cloud data warehouse — would reduce DB costs, enable cross-tenant aggregate analytics (anonymized), and unlock larger training windows for the LSTM without memory pressure.

**Change Data Capture (CDC)**
For enterprise source systems where polling is disruptive, a CDC pipeline (Debezium + Kafka Connect) would capture row-level changes from the customer's ERP without hitting production query load. Feeds directly into the existing ingest normalization layer.

**Multi-region tenancy and data residency**
The current RLS architecture is single-region. Enterprise buyers in regulated markets (EU, healthcare supply chains) require data residency controls and audit trails per region. Connection routing above `get_tenant_db` would need to support region-scoped shard selection.

---

## 2. Social Media and News Sentiment for Trend Prediction

The LSTM + XGBoost ensemble is trained exclusively on historical POS data. It has no signal for exogenous demand shocks — a product going viral on TikTok, a brand appearing in a major news cycle, or a celebrity endorsement can drain a store's inventory in 48 hours with zero historical precedent.

**Trend ingestion pipeline**
A new Celery beat job (likely every 4–6 hours) would pull from Google Trends, Reddit product/brand subreddits, TikTok hashtag trends, and Twitter/X brand mentions. Output is normalized to a per-SKU-category time series stored in TimescaleDB alongside POS data.

**Retail-specific sentiment model**
A lightweight fine-tuned transformer (DistilBERT or similar) trained on retail-relevant text would score incoming content for sentiment polarity and relevance to specific product categories. Point-in-time sentiment scores and velocity (rate of growth) become features.

**Viral coefficient as a feature**
The existing `detect_feature_tier()` function in `features.py` already handles tiered feature selection based on data depth. A third tier could activate social signal features — virality score, sentiment velocity, influencer exposure count — for tenants who opt in to external data enrichment.

**Early reorder trigger integration**
When social sentiment velocity exceeds a threshold AND on-hand stock is within normal ROP range, the optimizer in `optimizer.py` would surface an early reorder recommendation before the standard ROP trigger fires. This surfaces through the existing WebSocket alert pipeline.

**News event detection**
Financial and supply chain news (product recalls, brand acquisitions, commodity shortages) creates demand shocks that historical data cannot anticipate. NewsAPI or GDELT integration would pipe structured event signals into a separate feature column — effectively an exogenous event flag per SKU category and date.

**Pandera validation extension**
External signal data is noisier than POS data. A fourth Pandera gate (beyond the current three at raw → features → predictions) would enforce null rate, range, and staleness constraints on ingested social/news features before they enter the model.

---

## 3. Weather and Supply Chain Disruption Intelligence

Lead times in the current optimizer are treated as static inputs per vendor. In practice, a hurricane hitting a distribution corridor, a winter storm closing a regional DC, or port congestion on an import lane can add 5–10 days to delivery windows — and the model has no awareness of this until it shows up as late arrivals in historical data.

**Weather risk layer**
Integration with NOAA/NWS or a commercial provider (OpenWeatherMap, Tomorrow.io) would map each store, warehouse, and distribution center to a geographic zone. Forecast events are scored on severity × proximity × timing and stored as a risk signal in TimescaleDB.

**Dynamic lead time adjustment**
Lead time would become a probabilistic distribution rather than a point value. When a weather event is forecast along a supplier→DC→store route, the optimizer's ROP calculation would widen the safety stock buffer accordingly — ordering earlier without requiring manual override from a buyer.

**Supply chain network graph**
Modeling the supplier → DC → store network as a directed graph (NetworkX initially, Neo4j at scale) enables delay propagation: a weather event at one node automatically updates estimated arrival windows downstream. This feeds directly into the PO generation worker.

**Port and lane congestion signals**
For tenants with import-heavy SKU mixes, real-time shipping lane data (Freightos, Flexport, or public AIS vessel tracking) would surface congestion signals before they show up in missed deliveries. Same feed mechanism as weather risk — normalized to a lead time multiplier per supplier.

**Weather-demand correlation model**
Beyond disruption, weather also predicts demand: cold snaps drive hot beverage sales, storms drive generator and supply sales, heat waves shift beverage and cooling product mix. A weather-demand correlation model trained per SKU category would add a weather feature column to the 45-feature enriched tier in `features.py`.

**Proactive reorder escalation**
When weather risk + low stock + long supplier lead time align, the system would escalate from a standard ROP recommendation to a priority PO recommendation with a tighter delivery window requirement surfaced to the buyer.

---

## 4. ML and Platform Intelligence Expansions

**Federated learning across tenants**
Individual tenant models improve only from their own history. A federated learning layer would allow the shared demand model to learn from aggregate patterns across all tenants without exposing raw data between customers. Particularly valuable for new tenants with limited history — they would benefit from cross-tenant priors while the model warms up.

**Confidence intervals on predictions**
The current forecast output is a point estimate. Surfacing prediction uncertainty (e.g., 80% confidence intervals) would help buyers calibrate trust in model recommendations — especially for high-velocity or high-variance SKUs where the model is less certain.

**AutoML feature selection**
The 27/45 feature tier threshold in `detect_feature_tier()` is currently based on history depth. An AutoML layer could score feature importance dynamically per tenant and per SKU category, retiring low-signal features and promoting high-signal ones without requiring a code change.

**LLM-powered natural language insights**
A retrieval-augmented LLM layer grounded in the SHAP feature importance output would allow buyers to ask plain-language questions: "Why is product X projected to stock out?" or "What changed in my reorder recommendations this week?" The SHAP integration is already in place — this adds a language interface on top of it.

**Model explainability dashboard**
Extend the existing SHAP output from an API response into a dedicated dashboard view: per-SKU feature contribution waterfall charts, top drivers of the current forecast, and week-over-week driver change summaries. Directly improves enterprise buyer trust in automated PO recommendations.

**IoT and smart shelf integration**
Real-time weight or RFID sensors on shelves would eliminate the lag between a POS sale and an inventory count update — currently dependent on scan cadence. Sensor events would feed into the Kafka ingest pipeline alongside POS events, giving the forecasting model a higher-fidelity inventory signal.

---

## Sequencing Recommendation

These investments are not all equal in effort or return. A suggested sequencing based on current platform maturity and likely customer demand:

| Priority | Investment | Rationale |
|---|---|---|
| 1 | Weather + dynamic lead times | High signal-to-noise; low external data cost; directly improves core optimizer |
| 2 | Social sentiment pipeline | High ROI for trend-sensitive retail categories; differentiating feature for CPG buyers |
| 3 | Enterprise ERP connectors (SAP, NetSuite) | Required to unlock enterprise sales motion; framework already in place |
| 4 | Streaming ingestion (Kafka native) | Enables real-time dashboard and reduces forecast lag; builds on existing Kafka ingest |
| 5 | Confidence intervals + SHAP dashboard | Improves buyer trust; relatively low implementation cost given SHAP is already wired |
| 6 | Federated learning + LLM interface | Longer-term moat; requires stable multi-tenant deployment at scale first |
