from pathlib import Path

from scripts.generate_model_performance_log import build_entries, render_markdown


def test_build_entries_reads_registry_and_decisions(tmp_path: Path):
    models = tmp_path / "models"
    models.mkdir(parents=True, exist_ok=True)
    (models / "registry.json").write_text(
        """
{
  "models": [
    {
      "version": "v1",
      "model_name": "demand_forecast",
      "dataset": "favorita",
      "feature_tier": "cold_start",
      "rows_trained": 100,
      "mae": 1.2,
      "mape": 0.3,
      "status": "champion",
      "trained_at": "2026-02-10T00:00:00+00:00",
      "promoted_at": "2026-02-10T01:00:00+00:00"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    (models / "champion.json").write_text('{"version":"v1"}', encoding="utf-8")

    entries = build_entries(models)
    assert len(entries) == 1
    assert entries[0].decision == "promoted_to_champion"


def test_render_markdown_contains_decision_log_table():
    md = render_markdown([], "2026-02-15T00:00:00+00:00")
    assert "# Model Performance Log" in md
    assert "## Decision Log" in md
    assert "generate_model_performance_log.py" in md
