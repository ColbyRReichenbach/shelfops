from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.replenishment_simulation import (
    SimulationConfig,
    render_simulation_markdown,
    run_replenishment_simulation,
    simulate_replenishment_policies,
)


def _synthetic_frame() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2024-01-01", periods=84, freq="D")
    for store_id, product_id, base, weekly_bump, price in [
        ("S1", "P1", 5, 3, 4.0),
        ("S2", "P2", 3, 2, 6.0),
    ]:
        for idx, current_date in enumerate(dates):
            quantity = base + (weekly_bump if current_date.dayofweek in {4, 5} else 0) + (idx % 3 == 0)
            rows.append(
                {
                    "date": current_date,
                    "store_id": store_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "category": "GROCERY",
                    "is_promotional": int(current_date.dayofweek == 5),
                    "is_holiday": 0,
                    "dataset_id": "m5_walmart",
                    "country_code": "US",
                    "frequency": "daily",
                    "price": price,
                }
            )
    return pd.DataFrame(rows)


def test_simulation_outputs_required_metrics_and_labels():
    report = simulate_replenishment_policies(
        _synthetic_frame(),
        config=SimulationConfig(replay_days=21, warmup_days=42, max_series=2),
    )

    assert report["simulation_scope"] == "benchmark_replay"
    assert report["impact_confidence"] == "simulated"
    assert report["policy_version"] == "replenishment_v1"
    assert report["model_version"] == "v3"
    assert "policy_versions" in report
    assert "not measured merchant impact" in report["claim_boundary"].lower()
    assert "does not observe true live stockout status" in report["stockout_label_boundary"].lower()
    assert len(report["results"]) == 4

    policy_names = {row["policy_name"] for row in report["results"]}
    assert policy_names == {"static", "moving_average", "seasonal_naive", "shelfops_model"}

    for row in report["results"]:
        assert set(row.keys()) == {
            "policy_name",
            "stockout_days",
            "lost_sales_units",
            "lost_sales_proxy",
            "overstock_units",
            "overstock_dollars",
            "service_level",
            "po_count",
            "combined_cost_proxy",
        }
        assert 0.0 <= row["service_level"] <= 1.0
        assert row["po_count"] >= 0
        assert row["combined_cost_proxy"] >= 0


def test_simulation_script_writes_json_and_markdown(tmp_path: Path):
    data_dir = tmp_path / "dataset"
    data_dir.mkdir(parents=True)
    _synthetic_frame().to_csv(data_dir / "canonical_transactions.csv", index=False)

    output_json = tmp_path / "simulation.json"
    output_md = tmp_path / "simulation.md"
    report = run_replenishment_simulation(
        data_dir=data_dir,
        config=SimulationConfig(replay_days=21, warmup_days=42, max_series=2),
        output_json=output_json,
        output_md=output_md,
    )

    assert output_json.exists()
    assert output_md.exists()
    markdown = output_md.read_text()
    assert "# Replenishment Replay Simulation" in markdown
    assert "| policy | stockout_days |" in markdown
    assert "- policy_version: `replenishment_v1`" in markdown
    assert render_simulation_markdown(report) == markdown
