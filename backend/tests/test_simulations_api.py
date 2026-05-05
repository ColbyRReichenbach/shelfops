from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_replenishment_simulation import _synthetic_frame


@pytest.mark.asyncio
class TestSimulationsAPI:
    async def test_replenishment_simulation_refresh_runs_and_returns_report(self, client, tmp_path: Path):
        data_dir = tmp_path / "dataset"
        data_dir.mkdir(parents=True)
        _synthetic_frame().to_csv(data_dir / "canonical_transactions.csv", index=False)
        report_path = tmp_path / "report.json"

        response = await client.get(
            "/api/v1/simulations/replenishment",
            params={
                "refresh": "true",
                "data_dir": str(data_dir),
                "report_path": str(report_path),
                "replay_days": 21,
                "warmup_days": 42,
                "max_series": 2,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["simulation_scope"] == "benchmark_replay"
        assert payload["impact_confidence"] == "simulated"
        assert payload["policy_version"] == "replenishment_v1"
        assert len(payload["results"]) == 4
        assert report_path.exists()

    async def test_replenishment_simulation_reads_existing_report(self, client, tmp_path: Path):
        report_path = tmp_path / "report.json"
        report_path.write_text(
            json.dumps(
                {
                    "dataset_id": "m5_walmart",
                    "dataset_snapshot_id": "dsnap_test",
                    "simulation_scope": "benchmark_replay",
                    "impact_confidence": "simulated",
                    "claim_boundary": "Benchmark simulation only. Not measured merchant impact.",
                    "stockout_label_boundary": "M5 benchmark replay uses simulated inventory depletion.",
                    "inventory_assumptions_confidence": "simulated",
                    "po_assumptions_confidence": "simulated",
                    "lead_time_assumptions_confidence": "simulated",
                    "cost_assumptions_confidence": "simulated",
                    "model_version": "v3",
                    "policy_version": "replenishment_v1",
                    "policy_versions": ["replenishment_v1"],
                    "rows_used": 10,
                    "series_used": 1,
                    "history_start": "2024-01-01",
                    "history_end": "2024-02-01",
                    "replay_start": "2024-02-02",
                    "replay_end": "2024-02-20",
                    "results": [
                        {
                            "policy_name": "static",
                            "stockout_days": 1,
                            "lost_sales_units": 2.0,
                            "lost_sales_proxy": 3.5,
                            "overstock_units": 4.0,
                            "overstock_dollars": 0.2,
                            "service_level": 0.95,
                            "po_count": 3,
                            "combined_cost_proxy": 75.0,
                        }
                    ],
                }
            )
        )

        response = await client.get(
            "/api/v1/simulations/replenishment",
            params={"report_path": str(report_path)},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["dataset_snapshot_id"] == "dsnap_test"
        assert payload["results"][0]["policy_name"] == "static"
