#!/usr/bin/env python3
"""
Generate a reproducible model performance log markdown document.

Sources:
  - backend/models/registry.json
  - backend/models/champion.json
  - backend/reports/run_*.json (best-effort)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ModelEntry:
    version: str
    model_name: str
    dataset: str
    feature_tier: str
    rows_trained: int | None
    mae: float | None
    mape: float | None
    status: str
    trained_at: str | None
    promoted_at: str | None
    decision: str
    decision_basis: str


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_registry(models_dir: Path) -> list[dict[str, Any]]:
    registry = _load_json(models_dir / "registry.json", {"models": []})
    return registry.get("models", [])


def _read_champion(models_dir: Path) -> dict[str, Any]:
    return _load_json(models_dir / "champion.json", {})


def _decision_for_row(row: dict[str, Any], champion_version: str | None) -> tuple[str, str]:
    status = row.get("status", "unknown")
    version = row.get("version", "unknown")
    promoted_at = row.get("promoted_at")

    if status == "champion" and version == champion_version:
        if promoted_at:
            return "promoted_to_champion", "status=champion and champion pointer matches"
        return "champion_active", "status=champion and champion pointer matches"
    if status == "champion":
        return "historic_champion", "status=champion in registry"
    if status == "candidate":
        return "candidate_pending", "registered but not promoted yet"
    if status == "challenger":
        return "challenger_shadow", "candidate held for challenger/shadow evaluation"
    if status == "archived":
        return "archived", "previous model superseded by newer champion"
    return "unknown", "status not mapped"


def build_entries(models_dir: Path) -> list[ModelEntry]:
    rows = _read_registry(models_dir)
    champion = _read_champion(models_dir)
    champion_version = champion.get("version")

    entries: list[ModelEntry] = []
    for row in rows:
        decision, basis = _decision_for_row(row, champion_version)
        entries.append(
            ModelEntry(
                version=row.get("version", "unknown"),
                model_name=row.get("model_name", "demand_forecast"),
                dataset=row.get("dataset", "unknown"),
                feature_tier=row.get("feature_tier", "unknown"),
                rows_trained=row.get("rows_trained"),
                mae=row.get("mae"),
                mape=row.get("mape"),
                status=row.get("status", "unknown"),
                trained_at=row.get("trained_at"),
                promoted_at=row.get("promoted_at"),
                decision=decision,
                decision_basis=basis,
            )
        )

    entries.sort(key=lambda x: x.trained_at or "", reverse=False)
    return entries


def _fmt_float(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.6f}"


def render_markdown(entries: list[ModelEntry], generated_at: str) -> str:
    lines = [
        "# Model Performance Log",
        "",
        f"_Generated at: {generated_at}_",
        "",
        "This is the reproducible source-of-truth log for model performance and decision history.",
        "",
        "## Data Sources",
        "",
        "- `backend/models/registry.json` (version history + status)",
        "- `backend/models/champion.json` (active champion pointer)",
        "- `backend/reports/run_*.json` (training run artifacts; supplementary)",
        "",
        "## Rebuild Command",
        "",
        "```bash",
        "PYTHONPATH=backend python3 backend/scripts/generate_model_performance_log.py --output docs/MODEL_PERFORMANCE_LOG.md",
        "```",
        "",
        "## Decision Log",
        "",
        "| order | version | model_name | dataset | tier | rows_trained | mae | mape | status | trained_at | promoted_at | decision | decision_basis |",
        "|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---|",
    ]

    for idx, e in enumerate(entries, start=1):
        lines.append(
            f"| {idx} | {e.version} | {e.model_name} | {e.dataset} | {e.feature_tier} | "
            f"{e.rows_trained if e.rows_trained is not None else '-'} | {_fmt_float(e.mae)} | {_fmt_float(e.mape)} | "
            f"{e.status} | {e.trained_at or '-'} | {e.promoted_at or '-'} | {e.decision} | {e.decision_basis} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This log is append-only through `registry.json` updates; historical rows should never be deleted.",
            "- Champion/challenger operational state in Postgres (`model_versions`, `backtest_results`, `shadow_predictions`) is the runtime truth.",
            "- Public dataset metrics are training/evaluation evidence only and do not imply dashboard catalog expansion.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate model performance log markdown")
    parser.add_argument("--project-root", type=str, default=".", help="Project root path")
    parser.add_argument("--output", type=str, default="docs/MODEL_PERFORMANCE_LOG.md", help="Output markdown path")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    models_dir = root / "backend" / "models"
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries = build_entries(models_dir)
    generated_at = datetime.now(timezone.utc).isoformat()
    md = render_markdown(entries, generated_at)
    output_path.write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
