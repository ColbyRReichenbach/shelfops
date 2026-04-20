# ShelfOps Pilot Playbook

This playbook defines how ShelfOps should run a measured 6 to 8 week pilot with a real merchant. It is intentionally stricter than a demo script.

## Pilot Goal

Prove that ShelfOps can improve replenishment decisions for a real merchant by combining:

- usable data onboarding
- forecast and uncertainty evidence
- recommendation review workflow
- buyer-decision capture
- measured or clearly labeled provisional outcomes

## Minimum Data Required

Required:

- store list
- product catalog with stable IDs or SKUs
- daily or transactional sales history
- current inventory snapshots

Strongly preferred:

- purchase-order history
- supplier or lead-time context
- promotion flags
- cost fields for overstock and stockout estimation

Allowed ingestion paths in the current phase:

- CSV onboarding
- Square

## Pilot Phases

### Phase 0: Qualification

- confirm merchant data access and usage permission
- confirm at least one stable store/product identifier strategy
- confirm enough history exists to leave cold start

### Phase 1: Onboarding And Readiness

- map stores and products
- validate transactions and inventory data quality
- resolve unmapped or stale records
- establish readiness state and blockers

### Phase 2: Baseline Window

- observe current merchant replenishment behavior
- define baseline operating process
- capture baseline stockout, overstock, forecast, and buyer-workflow metrics

### Phase 3: Recommendation Trial

- generate replenishment recommendations
- require accept, edit, or reject decisions
- record reason codes and edit deltas

### Phase 4: Outcome Measurement

- compare recommendations to later demand and inventory outcomes
- separate measured metrics from estimated or provisional metrics
- do not blend benchmark replay with merchant results

### Phase 5: Review And Decision

- summarize merchant-facing results
- identify data gaps, policy gaps, and operational blockers
- decide whether to extend, expand, or stop

## Weekly Cadence

Every week should include:

- data freshness and mapping review
- recommendation review and buyer feedback
- outcome review on prior recommendations
- model and policy notes
- open blockers and owner

## Success Metrics

Operational metrics to track:

- recommendation acceptance rate
- edit rate and average edit distance
- time to decision
- stockout events
- stockout miss rate
- overstock exposure
- forecast WAPE and MASE

Evidence labeling rules:

- `measured` only for real merchant outcomes
- `estimated` only for model-derived business approximations
- `provisional` when the full outcome horizon has not closed
- `simulated` only for benchmark replay or synthetic assumptions

## Pilot Deliverables

At pilot close, ShelfOps should be able to produce:

- a measured outcome summary
- a data-readiness summary
- a recommendation-decision summary
- a model-evidence summary
- a case study draft using [docs/templates/CASE_STUDY_TEMPLATE.md](./docs/templates/CASE_STUDY_TEMPLATE.md)
