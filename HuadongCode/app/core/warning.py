"""Deterministic warning core pipeline."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ._io import build_artifact_hints, load_numeric_series

FLOOD_WARNING_LEVELS = {
    "blue": {"threshold_ratio": 0.5, "name": "blue_warning", "level": 1},
    "yellow": {"threshold_ratio": 0.7, "name": "yellow_warning", "level": 2},
    "orange": {"threshold_ratio": 0.85, "name": "orange_warning", "level": 3},
    "red": {"threshold_ratio": 1.0, "name": "red_warning", "level": 4},
}


def compute_spi(streamflow: Sequence[float], scale: int = 3) -> list[float]:
    if len(streamflow) < scale:
        return [0.0] * len(streamflow)
    arr = np.array(streamflow, dtype=float)
    global_mean = float(np.mean(arr))
    if global_mean <= 0:
        return [0.0] * len(streamflow)
    spi: list[float] = []
    for i in range(len(arr)):
        if i < scale - 1:
            spi.append(0.0)
            continue
        window = arr[max(0, i - scale + 1) : i + 1]
        window_mean = float(np.mean(window))
        window_std = float(np.std(window))
        if window_mean > 0 and window_std > 0:
            spi.append(float((np.log(window_mean) - np.log(global_mean)) / window_std))
        else:
            spi.append(0.0)
    return spi


def flood_warning(forecast_streamflow: Sequence[float], warning_threshold: float, lead_time_hours: int | None = None) -> dict:
    arr = np.array(forecast_streamflow, dtype=float)
    levels = [
        ("blue", warning_threshold * 0.5),
        ("yellow", warning_threshold * 0.7),
        ("orange", warning_threshold * 0.85),
        ("red", warning_threshold * 1.0),
    ]
    warning_events: list[dict] = []
    earliest_warning_time = None
    max_level = 0
    for level_name, threshold in levels:
        indices = np.where(arr >= threshold)[0]
        if len(indices) == 0:
            continue
        idx = int(indices[0])
        earliest_warning_time = idx if earliest_warning_time is None else min(earliest_warning_time, idx)
        info = FLOOD_WARNING_LEVELS[level_name]
        warning_events.append(
            {
                "level": info["level"],
                "name": info["name"],
                "threshold": float(threshold),
                "trigger_time_index": idx,
                "forecast_value": float(arr[idx]),
            }
        )
        max_level = max(max_level, int(info["level"]))
    level_map = {1: "blue", 2: "yellow", 3: "orange", 4: "red"}
    warning_level = "none" if not warning_events else level_map.get(max_level, "none")
    lead_time = earliest_warning_time
    if lead_time_hours is not None and lead_time is not None:
        lead_time = min(lead_time, lead_time_hours)
    return {
        "warning_level": warning_level,
        "warning_events": warning_events,
        "earliest_warning_time": earliest_warning_time,
        "lead_time": lead_time,
        "warning_threshold": float(warning_threshold),
    }


def drought_warning(streamflow: Sequence[float], spi_threshold: float = -1.0, scale: int = 3) -> dict:
    spi = compute_spi(streamflow, scale)
    arr = np.array(spi, dtype=float)
    levels = [("blue", -1.0), ("yellow", -1.5), ("orange", -2.0), ("red", -2.5)]
    warning_events: list[dict] = []
    earliest_warning_time = None
    max_level = 0
    for level_name, threshold in levels:
        if threshold < spi_threshold:
            continue
        indices = np.where(arr <= threshold)[0]
        if len(indices) == 0:
            continue
        idx = int(indices[0])
        earliest_warning_time = idx if earliest_warning_time is None else min(earliest_warning_time, idx)
        info = FLOOD_WARNING_LEVELS[level_name]
        warning_events.append(
            {
                "level": info["level"],
                "name": info["name"],
                "spi_threshold": float(threshold),
                "trigger_time_index": idx,
                "spi_value": float(arr[idx]),
            }
        )
        max_level = max(max_level, int(info["level"]))
    level_map = {1: "blue", 2: "yellow", 3: "orange", 4: "red"}
    warning_level = "none" if not warning_events else level_map.get(max_level, "none")
    return {
        "warning_level": warning_level,
        "warning_events": warning_events,
        "spi_values": spi,
        "drought_start_index": earliest_warning_time,
        "spi_threshold": float(spi_threshold),
    }


def get_warning_rules() -> dict:
    return {
        "flood_levels": FLOOD_WARNING_LEVELS,
        "default_flood_threshold": 1000.0,
        "default_spi_threshold": -1.0,
        "default_spi_scale": 3,
    }


def run_warning_pipeline(
    *,
    forecast_streamflow: Sequence[float] | str | None = None,
    forecast_path: str | None = None,
    forecast_column: str | None = None,
    warning_threshold: float = 1000.0,
    lead_time_hours: int | None = None,
    spi_threshold: float = -1.0,
    spi_scale: int = 3,
    artifact_dir: str | None = None,
    artifact_prefix: str = "warning",
) -> dict:
    if forecast_streamflow is None and forecast_path is None:
        raise ValueError("Provide forecast_streamflow or forecast_path.")
    source = forecast_streamflow if forecast_streamflow is not None else forecast_path
    series = load_numeric_series(source, column=forecast_column)
    flood = flood_warning(series, warning_threshold=warning_threshold, lead_time_hours=lead_time_hours)
    drought = drought_warning(series, spi_threshold=spi_threshold, scale=spi_scale)
    summary_text = f"Flood={flood['warning_level']}, drought={drought['warning_level']} for {len(series)} forecast steps."
    return {
        "summary_text": summary_text,
        "flood_warning": flood,
        "drought_warning": drought,
        "warning_rules": get_warning_rules(),
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "warning.json"),
        ),
    }
