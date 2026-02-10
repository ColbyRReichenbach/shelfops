"""
Analytics Chart Design System — Standardized Plotly visualizations.

All analysis outputs use these functions so charts are visually
consistent across notebooks, reports, and dashboard embeds.

Standard: Plotly primary, Matplotlib for SHAP only.
Theme: plotly_white, Inter font, Set2 categorical palette.

Usage:
    from ml.charts import (
        plot_forecast_vs_actual,
        plot_feature_importance,
        plot_error_distribution,
        plot_tier_comparison,
        plot_training_summary,
    )
"""

from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger()

# Lazy imports — only load Plotly when actually charting
_plotly_loaded = False

REPORTS_DIR = Path(__file__).parent.parent / "reports"

# ──────────────────────────────────────────────────────────────────────
# Design Tokens
# ──────────────────────────────────────────────────────────────────────

COLORS = {
    "primary": "#2563EB",      # Blue-600
    "secondary": "#7C3AED",    # Violet-600
    "success": "#059669",      # Emerald-600
    "warning": "#D97706",      # Amber-600
    "danger": "#DC2626",       # Red-600
    "neutral": "#6B7280",      # Gray-500
    "bg": "#FFFFFF",
    "grid": "#F3F4F6",         # Gray-100
}

# For categorical data — colorblind-friendly
CATEGORICAL_PALETTE = [
    "#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3",
    "#A6D854", "#FFD92F", "#E5C494", "#B3B3B3",
]

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"

LAYOUT_DEFAULTS = {
    "font": {"family": FONT_FAMILY, "size": 13, "color": "#1F2937"},
    "paper_bgcolor": COLORS["bg"],
    "plot_bgcolor": COLORS["bg"],
    "margin": {"l": 60, "r": 30, "t": 60, "b": 50},
    "xaxis": {
        "gridcolor": COLORS["grid"],
        "showline": True,
        "linecolor": "#E5E7EB",
    },
    "yaxis": {
        "gridcolor": COLORS["grid"],
        "showline": True,
        "linecolor": "#E5E7EB",
    },
}


def _ensure_plotly():
    """Import Plotly lazily."""
    global _plotly_loaded
    if not _plotly_loaded:
        import plotly.io as pio
        pio.templates.default = "plotly_white"
        _plotly_loaded = True


def _apply_defaults(fig: Any) -> Any:
    """Apply standard layout to a Plotly figure."""
    fig.update_layout(**LAYOUT_DEFAULTS)
    return fig


def _save(fig: Any, name: str, save_html: bool = True, save_png: bool = True) -> Path:
    """Save figure to reports/ as HTML and/or PNG."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    html_path = REPORTS_DIR / f"{name}.html"

    if save_html:
        fig.write_html(str(html_path), include_plotlyjs="cdn")

    if save_png:
        try:
            fig.write_image(str(REPORTS_DIR / f"{name}.png"), scale=2)
        except Exception:
            logger.warning("charts.png_export_failed", name=name,
                           hint="Install kaleido: pip install kaleido")

    return html_path


# ──────────────────────────────────────────────────────────────────────
# Chart Functions
# ──────────────────────────────────────────────────────────────────────

def plot_forecast_vs_actual(
    dates: list,
    actual: list[float],
    predicted: list[float],
    lower: list[float] | None = None,
    upper: list[float] | None = None,
    title: str = "Forecast vs Actual Demand",
) -> Any:
    """
    Line chart comparing predicted vs actual demand with
    optional confidence interval band.
    """
    _ensure_plotly()
    import plotly.graph_objects as go

    fig = go.Figure()

    # Confidence interval band
    if lower and upper:
        fig.add_trace(go.Scatter(
            x=list(dates) + list(reversed(dates)),
            y=list(upper) + list(reversed(lower)),
            fill="toself",
            fillcolor="rgba(37, 99, 235, 0.1)",
            line=dict(width=0),
            name="90% Confidence",
            showlegend=True,
        ))

    # Actual
    fig.add_trace(go.Scatter(
        x=dates,
        y=actual,
        mode="lines",
        name="Actual",
        line=dict(color=COLORS["neutral"], width=2),
    ))

    # Predicted
    fig.add_trace(go.Scatter(
        x=dates,
        y=predicted,
        mode="lines",
        name="Predicted",
        line=dict(color=COLORS["primary"], width=2.5),
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Demand (units)",
        legend=dict(orientation="h", y=1.02, x=0),
    )

    return _save(_apply_defaults(fig), "forecast_vs_actual")


def plot_feature_importance(
    importance: dict[str, float],
    top_n: int = 20,
    title: str = "Feature Importance (SHAP)",
) -> Any:
    """Horizontal bar chart of top N features by importance."""
    _ensure_plotly()
    import plotly.graph_objects as go

    # Sort and take top N
    sorted_items = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:top_n]
    features = [item[0] for item in reversed(sorted_items)]
    values = [item[1] for item in reversed(sorted_items)]

    fig = go.Figure(go.Bar(
        x=values,
        y=features,
        orientation="h",
        marker_color=COLORS["primary"],
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Mean |SHAP value|",
        yaxis_title="",
        height=max(400, top_n * 25),
    )

    return _save(_apply_defaults(fig), "feature_importance")


def plot_error_distribution(
    residuals: list[float],
    title: str = "Prediction Error Distribution",
) -> Any:
    """Histogram of prediction residuals (actual - predicted)."""
    _ensure_plotly()
    import plotly.graph_objects as go

    fig = go.Figure(go.Histogram(
        x=residuals,
        nbinsx=50,
        marker_color=COLORS["primary"],
        opacity=0.85,
    ))

    # Add zero line
    fig.add_vline(x=0, line_dash="dash", line_color=COLORS["danger"])

    # Add MAE annotation
    mae = float(np.mean(np.abs(residuals)))
    fig.add_annotation(
        x=0.95, y=0.95, xref="paper", yref="paper",
        text=f"MAE: {mae:.2f}",
        showarrow=False,
        font=dict(size=14, color=COLORS["primary"]),
        bgcolor="white",
        bordercolor=COLORS["primary"],
        borderwidth=1,
    )

    fig.update_layout(
        title=title,
        xaxis_title="Residual (Actual − Predicted)",
        yaxis_title="Count",
    )

    return _save(_apply_defaults(fig), "error_distribution")


def plot_tier_comparison(
    cold_start_metrics: dict[str, float],
    production_metrics: dict[str, float] | None = None,
    title: str = "Cold Start vs Production Model Performance",
) -> Any:
    """Grouped bar chart comparing metrics across tiers."""
    _ensure_plotly()
    import plotly.graph_objects as go

    metrics = ["mae", "mape"]
    cold_values = [cold_start_metrics.get(m, 0) for m in metrics]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=metrics,
        y=cold_values,
        name="Cold Start (27 features)",
        marker_color=COLORS["warning"],
    ))

    if production_metrics:
        prod_values = [production_metrics.get(m, 0) for m in metrics]
        fig.add_trace(go.Bar(
            x=metrics,
            y=prod_values,
            name="Production (46 features)",
            marker_color=COLORS["success"],
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Metric",
        yaxis_title="Value",
        barmode="group",
    )

    return _save(_apply_defaults(fig), "tier_comparison")


def plot_training_summary(
    params: dict[str, Any],
    metrics: dict[str, float],
    data_stats: dict[str, Any],
    title: str = "Training Run Summary",
) -> Any:
    """Table-style summary of a training run."""
    _ensure_plotly()
    import plotly.graph_objects as go

    # Combine all info into a table
    keys, values = [], []

    for k, v in params.items():
        keys.append(f"param/{k}")
        values.append(str(v))
    for k, v in metrics.items():
        if isinstance(v, float):
            keys.append(f"metric/{k}")
            values.append(f"{v:.4f}")
    for k, v in data_stats.items():
        keys.append(f"data/{k}")
        values.append(str(v))

    fig = go.Figure(go.Table(
        header=dict(
            values=["Key", "Value"],
            fill_color=COLORS["primary"],
            font=dict(color="white", size=13, family=FONT_FAMILY),
            align="left",
        ),
        cells=dict(
            values=[keys, values],
            fill_color=[COLORS["grid"], "white"],
            font=dict(size=12, family=FONT_FAMILY),
            align="left",
        ),
    ))

    fig.update_layout(title=title, height=max(300, len(keys) * 30))

    return _save(_apply_defaults(fig), "training_summary")
