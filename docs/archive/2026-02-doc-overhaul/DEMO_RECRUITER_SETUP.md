# Recruiter Demo Setup

Run one command to generate a recruiter-ready ML showcase:

```bash
PYTHONPATH=backend python3 backend/scripts/run_recruiter_demo.py --quick
```

Artifacts are written to:

- `docs/productization_artifacts/recruiter_demo/recruiter_demo_scorecard.json`
- `docs/productization_artifacts/recruiter_demo/recruiter_demo_scorecard.md`
- `docs/productization_artifacts/recruiter_demo/replay/replay_summary.json`

## What this command demonstrates

1. Initial model benchmarking (single dataset and pairwise combo support).
2. Model-family strategy cycle:
- XGBoost baseline
- LSTM challenger
- Ensemble weight sweep decision
3. Replay lifecycle proof:
- retrain trigger events
- promotion/HITL evidence
- production-style metrics contract outputs

## Interview flow (10-15 minutes)

1. Show `recruiter_demo_scorecard.md` first.
2. Open `model_strategy_cycle.md` and explain model-choice rationale.
3. Open replay summary and call out `retrain_count`, `baseline_gate_passed`, and `hitl_counts`.
4. Close with production controls:
- CI release gate
- runtime config validation
- migration/RLS checks
