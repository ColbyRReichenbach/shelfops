from __future__ import annotations

import pandas as pd

SERIES_KEYS = ["store_id", "product_id"]


def prepare_series_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values(SERIES_KEYS + ["date"], kind="mergesort").reset_index(drop=True)
    frame["_row_id"] = frame.index
    return frame


def naive_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    combined = pd.concat([train_df, test_df], ignore_index=True)
    shifted = combined.groupby(SERIES_KEYS)["quantity"].shift(1)
    fallback = train_df.groupby(SERIES_KEYS)["quantity"].last().rename("fallback")
    test = test_df.copy()
    test["pred"] = shifted.iloc[len(train_df) :].reset_index(drop=True)
    test = test.merge(fallback, on=SERIES_KEYS, how="left")
    global_mean = float(train_df["quantity"].mean()) if len(train_df) else 0.0
    return test["pred"].fillna(test["fallback"]).fillna(global_mean).clip(lower=0.0)


def seasonal_naive_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame, *, seasonality: int = 7) -> pd.Series:
    combined = pd.concat([train_df, test_df], ignore_index=True)
    seasonal = combined.groupby(SERIES_KEYS)["quantity"].shift(seasonality)
    lag1 = combined.groupby(SERIES_KEYS)["quantity"].shift(1)
    fallback = train_df.groupby(SERIES_KEYS)["quantity"].last().rename("fallback")
    test = test_df.copy()
    test["pred"] = seasonal.iloc[len(train_df) :].reset_index(drop=True)
    test["lag1"] = lag1.iloc[len(train_df) :].reset_index(drop=True)
    test = test.merge(fallback, on=SERIES_KEYS, how="left")
    global_mean = float(train_df["quantity"].mean()) if len(train_df) else 0.0
    return test["pred"].fillna(test["lag1"]).fillna(test["fallback"]).fillna(global_mean).clip(lower=0.0)


def moving_average_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame, *, window: int = 7) -> pd.Series:
    combined = pd.concat([train_df, test_df], ignore_index=True)
    rolling = combined.groupby(SERIES_KEYS)["quantity"].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )
    series_mean = train_df.groupby(SERIES_KEYS)["quantity"].mean().rename("series_mean")
    test = test_df.copy()
    test["pred"] = rolling.iloc[len(train_df) :].reset_index(drop=True)
    test = test.merge(series_mean, on=SERIES_KEYS, how="left")
    global_mean = float(train_df["quantity"].mean()) if len(train_df) else 0.0
    return test["pred"].fillna(test["series_mean"]).fillna(global_mean).clip(lower=0.0)


def category_store_average_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    test = test_df.copy()
    by_store_category = train_df.groupby(["store_id", "category"])["quantity"].mean().rename("store_category_mean")
    by_store = train_df.groupby("store_id")["quantity"].mean().rename("store_mean")
    by_category = train_df.groupby("category")["quantity"].mean().rename("category_mean")
    global_mean = float(train_df["quantity"].mean()) if len(train_df) else 0.0

    test = test.merge(by_store_category, on=["store_id", "category"], how="left")
    test = test.merge(by_store, on="store_id", how="left")
    test = test.merge(by_category, on="category", how="left")
    return (
        test["store_category_mean"]
        .fillna(test["store_mean"])
        .fillna(test["category_mean"])
        .fillna(global_mean)
        .clip(lower=0.0)
    )


def intermittent_demand_forecast(train_df: pd.DataFrame, test_df: pd.DataFrame) -> pd.Series:
    grouped = train_df.groupby(SERIES_KEYS)["quantity"]
    nonzero_prob = grouped.apply(lambda s: float((s > 0).mean())).rename("nonzero_prob")
    nonzero_mean = grouped.apply(lambda s: float(s[s > 0].mean()) if (s > 0).any() else 0.0).rename("nonzero_mean")
    test = test_df.copy()
    test = test.merge(nonzero_prob, on=SERIES_KEYS, how="left")
    test = test.merge(nonzero_mean, on=SERIES_KEYS, how="left")

    global_prob = float((train_df["quantity"] > 0).mean()) if len(train_df) else 0.0
    nonzero_train = train_df.loc[train_df["quantity"] > 0, "quantity"]
    global_nonzero_mean = float(nonzero_train.mean()) if len(nonzero_train) else 0.0
    pred = test["nonzero_prob"].fillna(global_prob) * test["nonzero_mean"].fillna(global_nonzero_mean)
    return pred.clip(lower=0.0)
