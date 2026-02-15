import json

from ml import experiment


def _write_registry(models_dir, models):
    models_dir.mkdir(parents=True, exist_ok=True)
    payload = {"models": models, "updated_at": None}
    (models_dir / "registry.json").write_text(json.dumps(payload), encoding="utf-8")


def test_sync_registry_promoted_updates_champion_pointer(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(experiment, "MODEL_DIR", models_dir)
    monkeypatch.setattr(experiment, "MODEL_PERFORMANCE_LOG_PATH", reports_dir / "MODEL_PERFORMANCE_LOG.md")

    _write_registry(
        models_dir,
        [
            {
                "version": "v1",
                "model_name": "demand_forecast",
                "status": "champion",
                "promoted_at": "2026-02-01T00:00:00+00:00",
            },
            {
                "version": "v2",
                "model_name": "demand_forecast",
                "status": "candidate",
                "promoted_at": None,
            },
        ],
    )
    (models_dir / "champion.json").write_text(
        json.dumps({"version": "v1", "promoted_at": "2026-02-01T00:00:00+00:00"}),
        encoding="utf-8",
    )

    experiment.sync_registry_with_runtime_state(
        version="v2",
        model_name="demand_forecast",
        candidate_status="champion",
        active_champion_version="v2",
        promotion_reason="passed_business_and_ds_gates",
    )

    registry = json.loads((models_dir / "registry.json").read_text(encoding="utf-8"))
    rows = {row["version"]: row for row in registry["models"]}
    assert rows["v1"]["status"] == "archived"
    assert rows["v2"]["status"] == "champion"
    assert rows["v2"]["promoted_at"]
    assert rows["v2"]["promotion_reason"] == "passed_business_and_ds_gates"

    champion = json.loads((models_dir / "champion.json").read_text(encoding="utf-8"))
    assert champion["version"] == "v2"
    assert (reports_dir / "MODEL_PERFORMANCE_LOG.md").exists()


def test_sync_registry_challenger_restores_runtime_champion(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(experiment, "MODEL_DIR", models_dir)
    monkeypatch.setattr(experiment, "MODEL_PERFORMANCE_LOG_PATH", reports_dir / "MODEL_PERFORMANCE_LOG.md")

    _write_registry(
        models_dir,
        [
            {
                "version": "v1",
                "model_name": "demand_forecast",
                "status": "champion",
                "promoted_at": "2026-02-01T00:00:00+00:00",
            },
            {
                "version": "v2",
                "model_name": "demand_forecast",
                "status": "champion",
                "promoted_at": "2026-02-10T00:00:00+00:00",
            },
        ],
    )
    (models_dir / "champion.json").write_text(
        json.dumps({"version": "v2", "promoted_at": "2026-02-10T00:00:00+00:00"}),
        encoding="utf-8",
    )

    experiment.sync_registry_with_runtime_state(
        version="v2",
        model_name="demand_forecast",
        candidate_status="challenger",
        active_champion_version="v1",
        promotion_reason="blocked_insufficient_accuracy_samples",
    )

    registry = json.loads((models_dir / "registry.json").read_text(encoding="utf-8"))
    rows = {row["version"]: row for row in registry["models"]}
    assert rows["v1"]["status"] == "champion"
    assert rows["v2"]["status"] == "challenger"
    assert rows["v2"]["promoted_at"] is None
    assert rows["v2"]["promotion_reason"] == "blocked_insufficient_accuracy_samples"

    champion = json.loads((models_dir / "champion.json").read_text(encoding="utf-8"))
    assert champion["version"] == "v1"
    assert (reports_dir / "MODEL_PERFORMANCE_LOG.md").exists()
