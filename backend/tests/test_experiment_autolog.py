import json

from ml import experiment


def test_register_model_auto_refreshes_performance_log(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    docs_dir = tmp_path / "docs"
    monkeypatch.setattr(experiment, "MODEL_DIR", models_dir)
    monkeypatch.setattr(experiment, "DOCS_DIR", docs_dir)
    monkeypatch.setattr(experiment, "MODEL_PERFORMANCE_LOG_PATH", docs_dir / "MODEL_PERFORMANCE_LOG.md")

    experiment.register_model(
        version="v1",
        feature_tier="cold_start",
        dataset="favorita",
        rows_trained=100,
        metrics={"mae": 1.23, "mape": 0.45},
        promote=True,
        model_name="demand_forecast",
    )

    assert (models_dir / "registry.json").exists()
    assert (models_dir / "champion.json").exists()
    assert (docs_dir / "MODEL_PERFORMANCE_LOG.md").exists()

    md = (docs_dir / "MODEL_PERFORMANCE_LOG.md").read_text(encoding="utf-8")
    assert "promoted_to_champion" in md
    assert "| 1 | v1 | demand_forecast | favorita | cold_start | 100 |" in md

    registry = json.loads((models_dir / "registry.json").read_text(encoding="utf-8"))
    assert registry["models"][0]["status"] == "champion"
