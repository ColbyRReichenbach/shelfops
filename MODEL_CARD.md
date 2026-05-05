# ShelfOps Model Card

## Active Champion

- Version: `v3`
- Model: `demand_forecast`
- Architecture: `lightgbm`
- Objective: `poisson`
- Status: `champion`
- Promoted at: `2026-04-19T23:52:34.979842+00:00`
- Promotion reason: `m5_subset20_holdout_beats_public_baselines`

## Training Data

- Dataset ID: `m5_walmart`
- Dataset snapshot ID: `dsnap_09e19c9147a57fe5`
- Canonical subset path: `data/benchmarks/m5_walmart/subset_20spc/canonical_transactions.csv`
- Raw subset manifest: `data/benchmarks/m5_walmart/subset_20spc/raw_subset/subset_manifest.json`
- Subset strategy: balanced store/category series sample
- Series per store/category: `20`
- Selected series: `600`
- Canonical rows trained: `1,147,800`
- Coverage: `2011-01-29` to `2016-04-24`
- Stores: `10`
- Products: `551`
- Categories: `3`

## Performance

- Cross-validation metrics from [backend/models/v3/metadata.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/models/v3/metadata.json):
  - `MAE 0.7011`
  - `WAPE 0.7415`
  - `MASE 0.8022`
  - `Bias % -0.0024`
  - `Interval method split_conformal`
  - `Interval coverage 0.9000`
- Public baseline benchmark from [backend/reports/m5_subset20_benchmark.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/reports/m5_subset20_benchmark.json):
  - strongest baseline on this subset: `moving_average_7`
  - baseline `WAPE 0.7548`
  - baseline `MASE 0.8265`
- Promotion holdout check from [backend/reports/m5_subset20_holdout_eval.json](/Users/colbyreichenbach/Downloads/shelfops_project/backend/reports/m5_subset20_holdout_eval.json):
  - cutoff: `2015-04-08`
  - holdout `MAE 0.8326`
  - holdout `WAPE 0.7276`
  - holdout `MASE 0.7968`
  - holdout `Bias % -0.0064`

## Feature Scope

- Feature tier: `cold_start`
- Feature count: `30`
- Main signals:
  - calendar/time features
  - lagged sales windows
  - rolling averages, volatility, and trend
  - category encoding
  - lagged buyer-decision trust features
- The active champion does not require tenant inventory or supplier fields, which keeps the public benchmark path aligned with M5 availability.

## Claim Boundaries

- This is benchmark evidence, not pilot evidence.
- M5 supports demand-forecasting accuracy work. It does not contain live inventory position, true stockout state, purchase orders, supplier lead times, or merchant financial outcomes.
- No claim in this model card should be interpreted as proof of real buyer ROI, PO optimization accuracy, or stockout prevention impact in a live merchant environment.
- Any future business-impact claims must come from explicitly labeled simulation or pilot data, not from this benchmark alone.

## Runtime Workspace

- The default benchmark workspace is loaded by `backend/scripts/bootstrap_benchmark_workspace.py`.
- Operational `transactions` rows contain positive M5 sales events only. Zero-demand M5 store-SKU-days remain in benchmark artifacts and model training/evaluation files; they are not represented as zero-quantity transactions because the runtime transaction table models events.
- Inventory, supplier, reorder-point, alert, recommendation, and historical outcome rows created around M5 are app scaffolding for walkthrough and policy testing. Treat those rows as `simulated` or `provisional`, not measured merchant outcomes.
- Runtime model evidence is synced with `backend/scripts/sync_benchmark_evidence_to_db.py`, which also seeds FreshRetailNet anomaly champion/challenger records and anomaly shadow-prediction persistence.
- Decision-aware benchmark experiments can be regenerated with `backend/scripts/run_decision_aware_experiment.py`; these reports combine forecast holdout metrics, uncertainty, segment metrics, and simulated replenishment replay, and remain shadow evidence until measured pilot outcomes exist.
- Manual and AI-assisted DS work can be governed through experiment context packages, source-labeled hypotheses, agent traces, and manual-vs-AI comparison reports. These are audit artifacts for reproducible experimentation, not proof of autonomous production promotion.
- Model Lab can persist immutable experiment specs for both current model families. M5 forecast specs bind feature windows, LightGBM objective/parameters, calibration strategy, and decision replay assumptions; FreshRetailNet anomaly specs bind detector feature flags, prior-sales lookback, score weights, thresholds, and promotion gates.

## Notes

- The repo previously pointed at a weaker demo-era champion. `v3` replaces that as the active file-based champion because it is M5-backed, uses real row counts, includes a dataset snapshot, and clears the public baseline comparison on the recorded holdout check.
- The active champion is based on a documented benchmark subset rather than the full 30,490-series M5 corpus. That tradeoff is explicit so local training remains reproducible while preserving full date-span coverage and all top-level store/category slices.
- Stockout-aware secondary evidence is documented separately in [MODEL_CARD_STOCKOUT_APPENDIX.md](/Users/colbyreichenbach/Downloads/shelfops_project/MODEL_CARD_STOCKOUT_APPENDIX.md) so it does not get blended into the M5 champion claim surface.
