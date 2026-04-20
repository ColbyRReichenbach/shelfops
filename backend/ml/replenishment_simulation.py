from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_DATA_DIR = "data/benchmarks/m5_walmart/subset_20spc"
DEFAULT_OUTPUT_JSON = "backend/reports/replenishment_simulation_m5.json"
DEFAULT_OUTPUT_MD = "backend/reports/replenishment_simulation_m5.md"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


@dataclass(frozen=True)
class SimulationConfig:
    dataset_id: str = "m5_walmart"
    model_version: str = "v3"
    policy_version: str = "replenishment_v1"
    lead_time_days: int = 5
    safety_stock_days: float = 2.0
    order_up_to_days: float = 7.0
    initial_inventory_days: float = 14.0
    order_cost: float = 24.0
    holding_cost_rate_annual: float = 0.25
    replay_days: int = 28
    warmup_days: int = 56
    max_series: int | None = 50


@dataclass(frozen=True)
class PolicyResult:
    policy_name: str
    stockout_days: int
    lost_sales_units: float
    lost_sales_proxy: float
    overstock_units: float
    overstock_dollars: float
    service_level: float
    po_count: int
    combined_cost_proxy: float


def load_canonical_transactions(data_dir: str | Path) -> pd.DataFrame:
    from ml.data_contracts import load_canonical_transactions as _load

    return _load(str(data_dir))


def prepare_replay_frame(df: pd.DataFrame, *, max_series: int | None = None) -> pd.DataFrame:
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0.0)
    if "price" in frame.columns:
        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    elif "sell_price" in frame.columns:
        frame["price"] = pd.to_numeric(frame["sell_price"], errors="coerce")
    else:
        frame["price"] = np.nan
    frame["unit_cost"] = frame["price"].fillna(0.0) * 0.7
    frame["series_id"] = frame["store_id"].astype(str) + "::" + frame["product_id"].astype(str)
    frame = frame.sort_values(["series_id", "date"]).reset_index(drop=True)
    if max_series:
        top_series = (
            frame.groupby("series_id")["quantity"].sum().sort_values(ascending=False).head(max_series).index.tolist()
        )
        frame = frame[frame["series_id"].isin(top_series)].reset_index(drop=True)
    return frame


def _time_split(frame: pd.DataFrame, config: SimulationConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_dates = sorted(frame["date"].dropna().unique().tolist())
    if len(unique_dates) < config.warmup_days + config.replay_days:
        raise ValueError("not enough history for requested warmup + replay window")
    replay_start = unique_dates[-config.replay_days]
    history = frame[frame["date"] < replay_start].copy()
    replay = frame[frame["date"] >= replay_start].copy()
    if history.empty or replay.empty:
        raise ValueError("replay split produced empty history or replay frame")
    return history.reset_index(drop=True), replay.reset_index(drop=True)


def _with_forecast_columns(full_frame: pd.DataFrame) -> pd.DataFrame:
    frame = full_frame.copy()
    grouped = frame.groupby("series_id")["quantity"]
    frame["forecast_moving_average"] = grouped.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    frame["forecast_seasonal_naive"] = grouped.shift(7)
    return frame


def _train_lightgbm_predictions(history: pd.DataFrame, replay: pd.DataFrame, full_frame: pd.DataFrame) -> pd.Series:
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("lightgbm is required for replenishment simulation") from exc

    frame = full_frame.copy()
    grouped = frame.groupby("series_id")["quantity"]
    frame["lag_1"] = grouped.shift(1)
    frame["lag_7"] = grouped.shift(7)
    frame["lag_28"] = grouped.shift(28)
    frame["rolling_mean_7"] = grouped.transform(lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    frame["rolling_mean_28"] = grouped.transform(lambda s: s.shift(1).rolling(28, min_periods=1).mean())
    frame["day_of_week"] = frame["date"].dt.dayofweek
    frame["month"] = frame["date"].dt.month
    frame["week_of_year"] = frame["date"].dt.isocalendar().week.astype(int)
    frame["store_code"] = pd.factorize(frame["store_id"])[0]
    frame["product_code"] = pd.factorize(frame["product_id"])[0]
    frame["category_code"] = pd.factorize(frame["category"].astype(str))[0]
    frame["is_promotional"] = pd.to_numeric(frame.get("is_promotional", 0), errors="coerce").fillna(0)
    frame["is_holiday"] = pd.to_numeric(frame.get("is_holiday", 0), errors="coerce").fillna(0)

    feature_cols = [
        "lag_1",
        "lag_7",
        "lag_28",
        "rolling_mean_7",
        "rolling_mean_28",
        "day_of_week",
        "month",
        "week_of_year",
        "store_code",
        "product_code",
        "category_code",
        "is_promotional",
        "is_holiday",
    ]
    train_mask = frame["date"] < replay["date"].min()
    predict_mask = frame["date"].isin(replay["date"].unique())
    train_df = frame.loc[train_mask].dropna(subset=["lag_1", "lag_7", "lag_28"]).copy()
    predict_df = frame.loc[predict_mask].copy()
    model = lgb.LGBMRegressor(
        objective="poisson",
        n_estimators=150,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        verbosity=-1,
    )
    model.fit(train_df[feature_cols].fillna(0.0), train_df["quantity"].astype(float))
    preds = model.predict(predict_df[feature_cols].fillna(0.0))
    out = pd.Series(np.maximum(preds, 0.0), index=predict_df.index)
    return out.reindex(replay.index).fillna(0.0)


def _static_daily_forecast(history: pd.DataFrame, replay: pd.DataFrame) -> pd.Series:
    history_means = history.groupby("series_id")["quantity"].mean().to_dict()
    return replay["series_id"].map(history_means).fillna(0.0).astype(float)


def _simulate_policy(
    replay: pd.DataFrame,
    *,
    forecast_col: str,
    config: SimulationConfig,
) -> PolicyResult:
    stockout_days = 0
    lost_sales_units = 0.0
    lost_sales_proxy = 0.0
    overstock_units = 0.0
    overstock_dollars = 0.0
    po_count = 0
    total_demand = 0.0
    total_sales = 0.0

    for _series_id, group in replay.groupby("series_id", sort=False):
        group = group.sort_values("date")
        avg_demand = float(group["forecast_static"].iloc[0] or 0.0)
        initial_inventory = max(1.0, math.ceil(avg_demand * config.initial_inventory_days))
        on_hand = float(initial_inventory)
        pending_orders: list[tuple[pd.Timestamp, float]] = []

        for row in group.itertuples(index=False):
            today = row.date
            arrivals_today = sum(qty for arrival_date, qty in pending_orders if arrival_date == today)
            if arrivals_today:
                on_hand += arrivals_today
            pending_orders = [(arrival_date, qty) for arrival_date, qty in pending_orders if arrival_date != today]
            on_order = sum(qty for _, qty in pending_orders)

            demand = float(row.quantity or 0.0)
            unit_price = float(row.price) if pd.notna(row.price) else 0.0
            unit_cost = float(row.unit_cost or 0.0)
            margin = ((unit_price - unit_cost) / unit_price) if unit_price > 0 and unit_cost >= 0 else 0.30

            sales = min(on_hand, demand)
            lost = max(0.0, demand - on_hand)
            on_hand = max(0.0, on_hand - sales)

            total_demand += demand
            total_sales += sales
            lost_sales_units += lost
            if lost > 0:
                stockout_days += 1
            lost_sales_proxy += lost * unit_price * max(0.0, margin)

            daily_forecast = max(0.0, float(getattr(row, forecast_col) or 0.0))
            safety_stock_units = daily_forecast * config.safety_stock_days
            reorder_point = daily_forecast * config.lead_time_days + safety_stock_units
            target_position = daily_forecast * (
                config.lead_time_days + config.order_up_to_days + config.safety_stock_days
            )
            inventory_position = on_hand + on_order

            excess_units = max(0.0, on_hand - safety_stock_units)
            overstock_units += excess_units
            overstock_dollars += excess_units * unit_cost * config.holding_cost_rate_annual / 365.0

            if inventory_position <= reorder_point:
                order_qty = max(1.0, math.ceil(target_position - inventory_position))
                arrival_date = today + pd.Timedelta(days=config.lead_time_days)
                pending_orders.append((arrival_date, order_qty))
                po_count += 1

    service_level = (total_sales / total_demand) if total_demand > 0 else 1.0
    combined_cost_proxy = lost_sales_proxy + overstock_dollars + po_count * config.order_cost
    return PolicyResult(
        policy_name=forecast_col.removeprefix("forecast_"),
        stockout_days=int(stockout_days),
        lost_sales_units=round(lost_sales_units, 4),
        lost_sales_proxy=round(lost_sales_proxy, 4),
        overstock_units=round(overstock_units, 4),
        overstock_dollars=round(overstock_dollars, 4),
        service_level=round(service_level, 6),
        po_count=int(po_count),
        combined_cost_proxy=round(combined_cost_proxy, 4),
    )


def simulate_replenishment_policies(df: pd.DataFrame, *, config: SimulationConfig) -> dict:
    frame = prepare_replay_frame(df, max_series=config.max_series)
    history, replay = _time_split(frame, config)
    full_frame = _with_forecast_columns(pd.concat([history, replay], ignore_index=True))
    history = full_frame.iloc[: len(history)].copy()
    replay = full_frame.iloc[len(history) :].copy()

    replay["forecast_static"] = _static_daily_forecast(history, replay)
    replay["forecast_shelfops_model"] = _train_lightgbm_predictions(history, replay, full_frame)
    replay["forecast_moving_average"] = replay["forecast_moving_average"].fillna(replay["forecast_static"])
    replay["forecast_seasonal_naive"] = replay["forecast_seasonal_naive"].fillna(replay["forecast_moving_average"])

    results = [
        _simulate_policy(replay, forecast_col="forecast_static", config=config),
        _simulate_policy(replay, forecast_col="forecast_moving_average", config=config),
        _simulate_policy(replay, forecast_col="forecast_seasonal_naive", config=config),
        _simulate_policy(replay, forecast_col="forecast_shelfops_model", config=config),
    ]
    dataset_snapshot_id = _resolve_dataset_snapshot_id(config.model_version)

    return {
        "dataset_id": config.dataset_id,
        "dataset_snapshot_id": dataset_snapshot_id,
        "simulation_scope": "benchmark_replay",
        "impact_confidence": "simulated",
        "claim_boundary": "Benchmark simulation only. Not measured merchant impact.",
        "inventory_assumptions_confidence": "simulated",
        "po_assumptions_confidence": "simulated",
        "lead_time_assumptions_confidence": "simulated",
        "cost_assumptions_confidence": "simulated",
        "model_version": config.model_version,
        "policy_version": config.policy_version,
        "policy_versions": [config.policy_version],
        "stockout_label_boundary": (
            "M5 benchmark replay uses simulated inventory depletion and lost-sales proxy. "
            "It does not observe true live stockout status."
            if config.dataset_id == "m5_walmart"
            else "Benchmark replay with dataset-specific stockout labels when available."
        ),
        "config": asdict(config),
        "rows_used": int(len(frame)),
        "series_used": int(frame["series_id"].nunique()),
        "history_start": str(history["date"].min().date()),
        "history_end": str(history["date"].max().date()),
        "replay_start": str(replay["date"].min().date()),
        "replay_end": str(replay["date"].max().date()),
        "results": [asdict(result) for result in results],
    }


def render_simulation_markdown(report: dict) -> str:
    lines = [
        "# Replenishment Replay Simulation",
        "",
        f"- dataset_id: `{report['dataset_id']}`",
        f"- simulation_scope: `{report['simulation_scope']}`",
        f"- impact_confidence: `{report['impact_confidence']}`",
        f"- dataset_snapshot_id: `{report.get('dataset_snapshot_id') or 'unavailable'}`",
        f"- model_version: `{report.get('model_version') or 'unavailable'}`",
        f"- policy_version: `{report.get('policy_version') or 'unavailable'}`",
        f"- claim_boundary: {report['claim_boundary']}",
        f"- stockout_label_boundary: {report['stockout_label_boundary']}",
        "",
        "| policy | stockout_days | lost_sales_proxy | overstock_units | overstock_dollars | service_level | po_count | combined_cost_proxy |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["results"]:
        lines.append(
            f"| {row['policy_name']} | {row['stockout_days']} | {row['lost_sales_proxy']:.2f} | "
            f"{row['overstock_units']:.2f} | {row['overstock_dollars']:.2f} | "
            f"{row['service_level']:.4f} | {row['po_count']} | {row['combined_cost_proxy']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def run_replenishment_simulation(
    *,
    data_dir: str | Path = DEFAULT_DATA_DIR,
    config: SimulationConfig | None = None,
    output_json: str | Path | None = None,
    output_md: str | Path | None = None,
) -> dict:
    active_config = config or SimulationConfig()
    raw = load_canonical_transactions(data_dir)
    report = simulate_replenishment_policies(raw, config=active_config)

    if output_json:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2) + "\n")
    if output_md:
        output_md = Path(output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_simulation_markdown(report))
    return report


def load_simulation_report(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def _resolve_dataset_snapshot_id(model_version: str) -> str | None:
    metadata_path = MODELS_DIR / model_version / "metadata.json"
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text())
    return metadata.get("dataset_snapshot_id")
