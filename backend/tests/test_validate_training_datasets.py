from pathlib import Path

from scripts.validate_training_datasets import DatasetResult, render_markdown, validate_dataset


def test_validate_dataset_marks_missing_directory(tmp_path: Path):
    result = validate_dataset("walmart", tmp_path / "does_not_exist")
    assert result.status == "missing"


def test_render_markdown_contains_table_row():
    rows = [
        DatasetResult(
            dataset_key="favorita",
            data_dir=Path("data/kaggle/favorita"),
            status="ready",
            message="Canonical contract valid",
            rows=10,
            stores=2,
            products=3,
            date_min="2024-01-01",
            date_max="2024-01-10",
            frequency="daily",
            country_code="EC",
        )
    ]
    md = render_markdown(rows)
    assert "| favorita | `data/kaggle/favorita` | `ready` | 10 | 2 | 3 |" in md
    assert "Public datasets are training/evaluation domains only" in md
