from __future__ import annotations

import pandas as pd

SERIES_KEYS = ["store_id", "product_id"]


def infer_segments(frame: pd.DataFrame, *, cold_start_threshold: int = 14) -> dict[str, pd.Series]:
    work = frame.copy()
    if "quantity" not in work.columns:
        raise ValueError("infer_segments requires a quantity column")

    summary = (
        work.groupby(SERIES_KEYS, dropna=False)
        .agg(
            obs_count=("quantity", "size"),
            avg_qty=("quantity", "mean"),
            total_qty=("quantity", "sum"),
            nonzero_rate=("quantity", lambda s: float((pd.to_numeric(s, errors="coerce").fillna(0.0) > 0).mean())),
        )
        .reset_index()
    )
    work = work.merge(summary, on=SERIES_KEYS, how="left")

    avg_qty = pd.to_numeric(work["avg_qty"], errors="coerce").fillna(0.0)
    total_qty = pd.to_numeric(work["total_qty"], errors="coerce").fillna(0.0)
    nonzero_rate = pd.to_numeric(work["nonzero_rate"], errors="coerce").fillna(0.0)
    obs_count = pd.to_numeric(work["obs_count"], errors="coerce").fillna(0)

    q33 = float(summary["avg_qty"].quantile(0.33)) if len(summary) else 0.0
    q66 = float(summary["avg_qty"].quantile(0.66)) if len(summary) else 0.0
    q75_total = float(summary["total_qty"].quantile(0.75)) if len(summary) else 0.0
    promo_series = (
        pd.to_numeric(work["is_promotional"], errors="coerce").fillna(0).astype(float)
        if "is_promotional" in work.columns
        else pd.Series([0.0] * len(work), index=work.index)
    )

    segments = {
        "fast": (avg_qty >= q66) & (nonzero_rate >= 0.6),
        "medium": (avg_qty >= q33) & (avg_qty < q66) & (nonzero_rate >= 0.35),
        "slow": (avg_qty < q33) & (nonzero_rate >= 0.2),
        "intermittent": nonzero_rate < 0.2,
        "cold_start": obs_count <= cold_start_threshold,
        "promoted": promo_series > 0,
        "high_volume": total_qty >= q75_total,
    }

    if "is_perishable" in work.columns:
        segments["perishable"] = pd.to_numeric(work["is_perishable"], errors="coerce").fillna(0).astype(float) > 0
    else:
        segments["perishable"] = pd.Series([False] * len(work), index=work.index)

    stockout_cols = [col for col in ["stockout_status", "is_stockout", "stockout_window"] if col in work.columns]
    if stockout_cols:
        raw = pd.Series([False] * len(work), index=work.index)
        for col in stockout_cols:
            values = work[col]
            if values.dtype == object:
                raw = raw | values.astype(str).str.lower().isin({"1", "true", "yes", "stockout", "window"})
            else:
                raw = raw | (pd.to_numeric(values, errors="coerce").fillna(0).astype(float) > 0)
        segments["stockout_window"] = raw
    else:
        segments["stockout_window"] = pd.Series([False] * len(work), index=work.index)

    return segments
