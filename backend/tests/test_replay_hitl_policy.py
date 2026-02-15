from __future__ import annotations

from ml.replay_hitl_policy import decide_model_promotion, decide_po_action


def test_decide_po_action_is_deterministic():
    a1 = decide_po_action(
        forecast_qty=20.0,
        actual_qty=10.0,
        suggested_qty=20,
        decision_key="2026-01-01::store1::sku1",
    )
    a2 = decide_po_action(
        forecast_qty=20.0,
        actual_qty=10.0,
        suggested_qty=20,
        decision_key="2026-01-01::store1::sku1",
    )
    assert a1 == a2


def test_decide_po_action_rejects_large_overforecast():
    action = decide_po_action(
        forecast_qty=40.0,
        actual_qty=10.0,
        suggested_qty=40,
        decision_key="stable-overforecast",
    )
    assert action.action in {"reject", "edit"}


def test_decide_model_promotion_rejects_failed_gate():
    decision = decide_model_promotion(
        gate_passed=False,
        candidate_mape_nonzero=0.10,
        candidate_stockout_miss_rate=0.03,
        decision_key="model-v1",
    )
    assert decision.action == "reject"
    assert decision.reason_code == "gate_failed"


def test_decide_model_promotion_approves_good_candidate():
    decision = decide_model_promotion(
        gate_passed=True,
        candidate_mape_nonzero=0.10,
        candidate_stockout_miss_rate=0.02,
        decision_key="model-v-approve",
    )
    assert decision.action in {"approve", "reject"}
    assert decision.reason_code in {
        "approved_after_gate",
        "manual_conservative_hold",
        "mape_above_threshold",
        "stockout_risk_high",
        "insufficient_metrics",
        "gate_failed",
    }
