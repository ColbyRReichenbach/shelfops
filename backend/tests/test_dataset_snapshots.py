from pathlib import Path

import pandas as pd

from ml.dataset_snapshots import compute_dataset_snapshot_hash, create_dataset_snapshot, persist_dataset_snapshot


def _fixture_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "store_id": "S1",
                "product_id": "SKU1",
                "quantity": 5,
                "dataset_id": "m5_walmart",
                "frequency": "daily",
            },
            {
                "date": "2026-01-02",
                "store_id": "S1",
                "product_id": "SKU2",
                "quantity": 7,
                "dataset_id": "m5_walmart",
                "frequency": "daily",
            },
        ]
    )


def test_snapshot_hash_is_stable_for_same_rows():
    df = _fixture_df()
    hash_a = compute_dataset_snapshot_hash(df)
    hash_b = compute_dataset_snapshot_hash(df.sample(frac=1.0, random_state=42))
    assert hash_a == hash_b


def test_create_dataset_snapshot_includes_provenance_and_claim_boundaries(tmp_path: Path):
    snapshot = create_dataset_snapshot(_fixture_df(), dataset_id="m5_walmart")
    assert snapshot["snapshot_id"].startswith("dsnap_")
    assert snapshot["source_type"] == "benchmark"
    assert snapshot["geography"] == "US"
    assert snapshot["implementation_status"] == "benchmark_active"
    assert snapshot["claim_boundaries_ref"] == "data_registry/datasets.yaml"

    path = persist_dataset_snapshot(snapshot, output_dir=tmp_path)
    assert path.exists()


def test_snapshot_hash_supports_array_like_columns():
    df = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "store_id": "S1",
                "product_id": "SKU1",
                "quantity": 5,
                "hours_sale": [0, 1, 2],
                "hours_stock_status": [0, 0, 1],
            }
        ]
    )
    snapshot_hash = compute_dataset_snapshot_hash(df)
    assert isinstance(snapshot_hash, str)
    assert len(snapshot_hash) == 64
