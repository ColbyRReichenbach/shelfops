# ShelfOps — Future Integrations & Platform Vision

- Last verified date: March 9, 2026
- Audience: builders, stakeholders, technical reviewers
- Scope: later-phase expansion ideas beyond demo sign-off and first SMB-pilot hardening
- Source of truth: current boundaries in `docs/product/known_limitations.md` and active platform architecture

These are not committed deliveries. They are credible expansion paths once the current SMB-focused platform is stable.

## Priority Themes

### 1. Integration and platform scale
- Native ERP and larger POS connectors.
- More durable streaming ingestion than scheduled polling alone.
- Multi-region and data-residency-aware tenancy if enterprise rollout ever becomes a real target.

### 2. Better operational inputs
- Weather and supply-chain disruption signals for lead-time adjustment.
- Stronger external demand signals such as news, search, or social trend data.
- Higher-fidelity inventory inputs such as IoT or shelf-sensing data if the target segment justifies it.

### 3. Model maturity
- Calibrated prediction intervals.
- Cross-tenant pretraining or transfer learning for low-history tenants.
- More dynamic feature selection and challenger experimentation once tenant telemetry is deeper.

### 4. Explainability and buyer trust
- Buyer-facing uncertainty surfaces.
- Richer explanation views beyond technical ML Ops screens.
- Plain-language operational summaries grounded in existing model evidence and audit trails.

## Recommended Sequence

1. Weather and dynamic lead-time logic.
2. Confidence intervals and better buyer-facing explanation.
3. Native ERP/POS connector expansion.
4. Streaming-first ingest hardening.
5. Cross-tenant learning and richer external-demand signals.

## Rule

Do not present these items as committed roadmap dates or current capabilities.
