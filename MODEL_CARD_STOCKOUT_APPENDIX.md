# FreshRetailNet Stockout Appendix

## Purpose

This appendix records ShelfOps' secondary stockout-aware benchmark track using FreshRetailNet-50K.

Use it to support:

- stockout-aware evaluation
- censored-demand methodology
- perishable, promo, and weather-aware analysis

Do not use it to claim:

- U.S. merchant ROI
- measured pilot impact
- complete end-to-end replenishment proof

## Dataset Scope

- Dataset ID: `freshretailnet_50k`
- Source files: `data/benchmarks/freshretailnet_50k/raw/train.parquet`, `data/benchmarks/freshretailnet_50k/raw/eval.parquet`
- Benchmark snapshot ID: `dsnap_80ba1c489deb6f33`
- Benchmark subset: `5000` store-product series
- Rows used: `450,000` train, `35,000` eval
- Geography: non-U.S.
- Grain used in ShelfOps: store-product-day with preserved hourly stockout context

## Method

- The adapter preserves daily sales, stockout-hour counts, hourly stock-status traces, discount/activity flags, holiday flags, weather fields, and category hierarchy.
- The benchmark compares observed-demand baselines against a conservative latent-demand adjustment.
- The latent-demand adjustment is explicitly estimated:
  it uses non-stockout hourly sales rates from the training split to recover only a capped portion of likely lost demand during stockout hours.

## Benchmark Results

Source: [backend/reports/freshretailnet_stockout_benchmark.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/reports/freshretailnet_stockout_benchmark.json)

- `moving_average_7_observed` is the best pure observed-demand baseline on overall error:
  `WAPE 0.3487`, `MASE 0.3441`
- `moving_average_7_latent_adjusted` has slightly worse overall error:
  `WAPE 0.3587`, `MASE 0.3540`
- But the latent-adjusted path reduces stockout underforecast pressure:
  `underforecast_rate_during_stockouts 0.4363` vs `0.5130`
- The latent-adjusted path also shrinks the estimated recovered-demand gap:
  `-0.2375` vs `-0.3518`

Interpretation:

- observed-demand baselines remain stronger on headline forecast error
- the conservative stockout-aware adjustment improves stockout-window sensitivity
- this is methodology evidence, not business-impact evidence

## Anomaly Detector Evidence

Source: [backend/reports/freshretailnet_anomaly_benchmark.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/reports/freshretailnet_anomaly_benchmark.json)

- Active anomaly champion: `anomaly_detector:a1`
- Shadow challenger: `anomaly_detector:a2`
- Evaluation rows after prior-window feature readiness: `142,856`
- Champion threshold: `0.55`
- Champion precision: `0.7409`
- Champion recall: `0.0799`
- Champion false-positive rate: `0.0213`
- Champion review rate: `0.0466`
- Challenger threshold: `0.35`
- Challenger precision: `0.5052`
- Challenger recall: `0.1601`
- Challenger false-positive rate: `0.1194`
- Challenger review rate: `0.1370`

Interpretation:

- `a1` stays champion because low false-positive workload matters for SMB cycle counts.
- `a2` remains in shadow because it catches more labeled stockout events but asks the operator to review more items.
- Model Lab can now run FreshRetailNet anomaly experiments from immutable spec
  templates. The spec controls detector feature flags, prior-sales lookback,
  score weights, threshold, promotion gates, and lineage hash.
- The runtime database now persists anomaly detection runs and shadow-prediction rows so real cycle-count feedback can later update measured anomaly precision.
- Current anomaly feedback provenance is `benchmark` / `unavailable`, not measured merchant feedback.

## Claim Boundaries

- FreshRetailNet is a secondary evidence track. It does not replace the active M5-backed champion.
- The recovered-demand comparison is estimated against a conservative proxy, not against directly observed true latent demand.
- The stockout-aware benchmark should be shown separately from M5 forecasting evidence rather than blended into the champion headline metrics.
- FreshRetailNet anomaly labels support benchmark precision/recall/FPR claims only. They do not prove U.S. SMB shelf availability, shrink reduction, or buyer ROI.
