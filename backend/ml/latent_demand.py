from __future__ import annotations

import numpy as np
import pandas as pd


SERIES_KEYS = ["store_id", "product_id"]
ACTIVE_HOURS_COUNT = 17


def add_conservative_latent_demand(
    frame: pd.DataFrame,
    *,
    actual_col: str = "quantity",
    stockout_hours_col: str = "stockout_hours_6_22",
    split_col: str | None = None,
    max_uplift_pct: float = 0.5,
) -> pd.DataFrame:
    """
    Estimate a conservative latent-demand target for stockout windows.

    Method:
    - derive a non-stockout hourly sales rate from trailing in-stock observations
    - estimate lost sales only during stockout hours
    - cap uplift to avoid implausible demand inflation
    """
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.sort_values(SERIES_KEYS + ["date"], kind="mergesort").reset_index(drop=True)

    quantity = pd.to_numeric(work[actual_col], errors="coerce").fillna(0.0)
    stockout_hours = pd.to_numeric(work[stockout_hours_col], errors="coerce").fillna(0.0).clip(lower=0, upper=ACTIVE_HOURS_COUNT)
    available_hours = (ACTIVE_HOURS_COUNT - stockout_hours).clip(lower=1.0)

    observed_rate = quantity / available_hours
    stockout_mask = stockout_hours > 0
    reference_rate = observed_rate.where(~stockout_mask)

    if split_col and split_col in work.columns:
        train_mask = work[split_col].astype(str) == "train"
        reference_rate = reference_rate.where(train_mask)

    work["_observed_hourly_rate"] = observed_rate
    work["_reference_hourly_rate"] = reference_rate

    ref_columns = SERIES_KEYS + ["category", "_reference_hourly_rate"]
    if split_col and split_col in work.columns:
        ref_columns.append(split_col)
    reference_frame = work.loc[work["_reference_hourly_rate"].notna(), ref_columns].copy()
    if split_col and split_col in work.columns:
        reference_frame = reference_frame.loc[reference_frame[split_col].astype(str) == "train"].copy()
    series_reference = (
        reference_frame.groupby(SERIES_KEYS, dropna=False)["_reference_hourly_rate"].median().rename("_series_reference_rate")
        if not reference_frame.empty
        else pd.Series(dtype="float64", name="_series_reference_rate")
    )
    category_reference = (
        reference_frame.groupby("category", dropna=False)["_reference_hourly_rate"].median().rename("_category_reference_rate")
        if not reference_frame.empty
        else pd.Series(dtype="float64", name="_category_reference_rate")
    )

    work = work.merge(series_reference, on=SERIES_KEYS, how="left")
    if "category" in work.columns:
        work = work.merge(category_reference, on="category", how="left")
    global_reference = float(reference_frame["_reference_hourly_rate"].median()) if not reference_frame.empty else 0.0
    baseline_rate = (
        work.get("_series_reference_rate", pd.Series([pd.NA] * len(work), index=work.index))
        .fillna(work.get("_category_reference_rate", pd.Series([pd.NA] * len(work), index=work.index)))
        .fillna(global_reference)
    )
    recovered_units = (baseline_rate * stockout_hours).clip(lower=0.0)
    capped_recovered_units = np.minimum(recovered_units, quantity * max_uplift_pct + recovered_units.clip(upper=1.0))

    work["latent_demand_quantity"] = quantity + capped_recovered_units.where(stockout_mask, 0.0)
    work["estimated_recovered_units"] = capped_recovered_units.where(stockout_mask, 0.0)
    work["latent_demand_method"] = "conservative_stockout_hourly_rate"

    return work.drop(
        columns=[
            "_observed_hourly_rate",
            "_reference_hourly_rate",
            "_series_reference_rate",
            "_category_reference_rate",
        ],
        errors="ignore",
    )
