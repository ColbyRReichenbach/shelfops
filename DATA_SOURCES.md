# ShelfOps Data Sources

Last updated: 2026-04-19

This file defines the active data scope for ShelfOps.

## Active Scope

ShelfOps currently treats the following as the only active data path for the
target product:

| Source | Role | Status | Allowed claims | Not enough to prove |
|---|---|---|---|---|
| `M5 / Walmart` | Primary public forecasting benchmark | active benchmark target | Benchmark forecasting accuracy, baselines, segments, uncertainty evaluation, reproducible dataset snapshots | Inventory position, purchase-order behavior, supplier lead times, real merchant ROI |
| `FreshRetailNet-50K` | Secondary public stockout/censored-demand benchmark | active benchmark target | Stockout-aware evaluation, censored-demand methodology, perishable/promo/weather-aware analysis | U.S. merchant ROI, complete SMB operating workflow |
| `CSV onboarding` | Pilot/product validation path | active product path | Merchant onboarding readiness, canonicalization, mapping, validation, shadow evaluation | Public benchmark accuracy by itself |
| `Square connector` | Pilot/product validation path | active product path | Real connector surface, OAuth/webhook/sync readiness, pilot ingestion path | Measured merchant impact until a real pilot is run and outcomes are observed |
| `Dominick's Finer Foods` | Deferred optional backup dataset | deferred | Optional future price/promo/margin backup evidence | Current active benchmark story |

## Legacy / Reference Only

| Source | Status | Rule |
|---|---|---|
| `Favorita` | legacy/reference only | Do not use as the active champion dataset or active public evidence path. |
| `Rossmann` | out of active scope | Too store-level for the core SKU replenishment loop. |
| `Instacart` | out of active scope | Useful for basket/reorder behavior, not replenishment evidence. |
| `84.51 Complete Journey` | out of active scope | Useful for campaign/basket analysis, not needed for the first ShelfOps loop. |
| `UCI Online Retail` | out of active scope | Too weak for the inventory-decision claim. |
| leaked or unauthorized proprietary data | disallowed | Never use for active implementation or public claims. |

## Claim Boundaries

- Benchmark evidence must be labeled `benchmark`.
- Stockout/censored-demand findings from FreshRetailNet must be labeled
  `benchmark` and must not be presented as measured merchant outcomes.
- CSV and Square only become `measured` pilot evidence when a real merchant
  authorizes the data flow and later outcomes are observed.
- Simulated or demo metrics must be labeled `simulated`, `estimated`, or
  `provisional`.
- Favorita may remain in the repo only as legacy reference material.

## Current Direction

The active build should use:

- `M5 / Walmart` for the primary benchmark-backed model reset
- `FreshRetailNet-50K` for stockout-aware evaluation
- `CSV onboarding` and `Square` for pilot-grade product validation

If a dataset or connector is not listed above, it is not part of the active
ShelfOps standout path.
