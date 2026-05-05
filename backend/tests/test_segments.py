import pandas as pd

from ml.segments import infer_segments


def test_infer_segments_assigns_core_flags():
    frame = pd.DataFrame(
        [
            {"date": "2026-01-01", "store_id": "S1", "product_id": "A", "quantity": 10, "is_promotional": 1},
            {"date": "2026-01-02", "store_id": "S1", "product_id": "A", "quantity": 11, "is_promotional": 0},
            {"date": "2026-01-03", "store_id": "S1", "product_id": "B", "quantity": 0, "is_promotional": 0},
            {"date": "2026-01-04", "store_id": "S1", "product_id": "B", "quantity": 0, "is_promotional": 0},
            {"date": "2026-01-05", "store_id": "S2", "product_id": "C", "quantity": 2, "is_promotional": 0},
            {"date": "2026-01-06", "store_id": "S2", "product_id": "C", "quantity": 3, "is_promotional": 0},
        ]
    )
    segments = infer_segments(frame, cold_start_threshold=3)
    assert set(["fast", "medium", "slow", "intermittent", "cold_start", "promoted", "high_volume"]).issubset(
        segments.keys()
    )
    assert bool(segments["promoted"].iloc[0]) is True
    assert segments["cold_start"].all()
    assert segments["intermittent"].iloc[2]
