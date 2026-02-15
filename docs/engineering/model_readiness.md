# ShelfOps Model Readiness

- Last verified date: February 15, 2026
- Audience: ML engineers and reviewers
- Scope: current readiness state by model/component family
- Source of truth: backend ML modules and associated tests

## Status Definitions

- `implemented`: usable with current dataset and workflow evidence
- `partial`: functional but pending telemetry depth or rollout controls
- `pilot_validated`: deterministic validation exists, but broad GA claims are not allowed
- `blocked`: not acceptable for production claim

## Readiness Matrix

| Component | Status | Notes |
|---|---|---|
| Demand forecast core (`train.py`, `predict.py`) | `implemented` | Active train/infer paths and runtime loop coverage. |
| Backtest and promotion arena | `implemented` | Business + DS gate enforcement in place. |
| Retraining event audit trail (`model_retraining_log`) | `implemented` | Retrain worker persists trigger/status/version events for runtime health APIs. |
| Model iteration diagnostics (`backend/reports/*/run_*.json`) | `implemented` | Training/run traces are available for iteration and regression triage. |
| Contract profiles and mapper | `implemented` | Profile-driven mapping and DQ gates are active. |
| Explainability export path | `implemented` | Feature importance and report paths are implemented. |
| File registry parity with DB promotion lifecycle | `implemented` | Runtime retrain flow synchronizes file artifacts with DB lifecycle state. |
| Anomaly detection calibration | `partial` | Logic exists; sustained labeled telemetry is still limited. |
| Feedback loop depth | `partial` | Outcome flow exists; richer closed-loop calibration remains. |
| Broad enterprise onboarding operations | `blocked` | Non-GA by product policy. |

## Communication Rule

Each external model claim must include one status label from this taxonomy (`implemented` policy).
