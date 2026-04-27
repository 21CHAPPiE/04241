from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from project.tanken_config import TankenCase


def _discover_repo_root() -> Path:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists() and (candidate / "data").exists():
            return candidate.resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _discover_repo_root()
PROJECT_DIR = REPO_ROOT / "project"
DEFAULT_EVENT_DIR = REPO_ROOT / "data" / "flood_event"


def resolve_event_path(event_csv_path: str | Path | None, case: "TankenCase") -> Path:
    if event_csv_path is None:
        default_candidate = Path(case.default_event)
        if default_candidate.is_absolute():
            return default_candidate
        repo_candidate = (REPO_ROOT / default_candidate).resolve()
        if repo_candidate.exists():
            return repo_candidate
        data_candidate = (REPO_ROOT / "data" / default_candidate).resolve()
        if data_candidate.exists():
            return data_candidate
        return (DEFAULT_EVENT_DIR / case.default_event).resolve()
    candidate = Path(event_csv_path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def clean_numeric_series(values: list[float | None], *, fallback: float = 0.0) -> list[float]:
    cleaned: list[float] = []
    last_value = float(fallback)
    for value in values:
        if value is None:
            cleaned.append(last_value)
            continue
        last_value = float(value)
        cleaned.append(last_value)
    return cleaned


def detect_weather_signal(rows: list[Any]) -> dict[str, Any]:
    prcp_values = [float(row.prcp) for row in rows if row.prcp is not None]
    inflow_values = [float(row.inflow) for row in rows if row.inflow is not None]
    max_prcp = max(prcp_values) if prcp_values else 0.0
    max_inflow = max(inflow_values) if inflow_values else 0.0
    severe = max_prcp >= 10.0 or max_inflow >= 1000.0
    return {
        "severe_weather": severe,
        "max_prcp_mm": round(max_prcp, 2),
        "max_inflow_m3s": round(max_inflow, 2),
    }


def benchmark_source(case: "TankenCase") -> str:
    return f"project/target.md#{case.case_id}"


def read_raw_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def estimate_interval_flow_series(rows: list[Any], season: str) -> list[float]:
    inflows = clean_numeric_series([row.inflow for row in rows])
    prcp_values = clean_numeric_series([row.prcp for row in rows], fallback=0.0)
    ratio = 0.35 if season == "plum_flood" else 0.2
    return [round(max(inflow * ratio, prcp * 25.0), 3) for inflow, prcp in zip(inflows, prcp_values)]
