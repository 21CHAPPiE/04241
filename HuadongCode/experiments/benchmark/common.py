"""Shared helpers for FastMCP benchmark scenarios."""

from __future__ import annotations

import asyncio
import csv
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.server import create_server
from app.io import write_json_artifact, write_text_artifact

TIMESTAMP_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)

_SERVER = create_server()


def parse_timestamp(raw_value: str) -> datetime:
    value = raw_value.strip()
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp format: {raw_value}")


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv_rows(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return target


def _slice_rows(
    *,
    input_path: str | Path,
    output_path: str | Path,
    time_column: str,
    start_time: str,
    end_time: str,
) -> Path:
    rows = read_csv_rows(input_path)
    start_dt = parse_timestamp(start_time)
    end_dt = parse_timestamp(end_time)
    selected = [
        row
        for row in rows
        if start_dt <= parse_timestamp(str(row[time_column])) <= end_dt
    ]
    if not selected:
        raise ValueError(f"No rows selected from {input_path} between {start_time} and {end_time}")
    return write_csv_rows(output_path, selected, list(selected[0].keys()))


def slice_basin_dataset(input_path: str | Path, start_time: str, end_time: str, output_path: str | Path) -> Path:
    return _slice_rows(
        input_path=input_path,
        output_path=output_path,
        time_column="time",
        start_time=start_time,
        end_time=end_time,
    )


def slice_multistation_dataset(input_path: str | Path, start_time: str, end_time: str, output_path: str | Path) -> Path:
    return _slice_rows(
        input_path=input_path,
        output_path=output_path,
        time_column="Time",
        start_time=start_time,
        end_time=end_time,
    )


def build_benchmark_run_root(scenario_name: str, output_root: str | Path | None = None) -> Path:
    base = Path(output_root) if output_root is not None else Path("experiments") / "benchmark" / "results"
    run_id = f"{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    scenario_dir = (base / scenario_name / run_id).resolve()
    scenario_dir.mkdir(parents=True, exist_ok=False)
    return scenario_dir


def _call_tool_async(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        result = await _SERVER.call_tool(name, arguments)
        if not isinstance(result.structured_content, dict):
            raise TypeError(f"Tool {name} did not return structured_content dict")
        return dict(result.structured_content)

    return asyncio.run(_run())


def call_fastmcp_tool(name: str, **arguments: Any) -> dict[str, Any]:
    clean_args = {key: value for key, value in arguments.items() if value is not None}
    return _call_tool_async(name, clean_args)


def load_artifact_csv(path: str | Path) -> list[dict[str, str]]:
    return read_csv_rows(path)


def load_artifact_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _timestamp_or_index(row: dict[str, str], index: int) -> str:
    for key in ("timestamp", "time", "Time"):
        raw = row.get(key)
        if raw:
            return raw
    return str(row.get("index", index))


def summarize_peak_and_window(csv_path: str | Path, value_column: str) -> dict[str, Any]:
    rows = load_artifact_csv(csv_path)
    numeric_rows: list[tuple[int, str, float]] = []
    for idx, row in enumerate(rows):
        raw = row.get(value_column)
        if raw in (None, ""):
            continue
        numeric_rows.append((idx, _timestamp_or_index(row, idx), float(raw)))
    if not numeric_rows:
        return {
            "value_column": value_column,
            "peak_value": None,
            "peak_position": None,
            "start_value": None,
            "end_value": None,
            "mean_value": None,
            "n_values": 0,
        }
    peak_idx, peak_position, peak_value = max(numeric_rows, key=lambda item: item[2])
    values = [item[2] for item in numeric_rows]
    return {
        "value_column": value_column,
        "peak_value": round(peak_value, 3),
        "peak_position": peak_position,
        "peak_index": peak_idx,
        "start_value": round(values[0], 3),
        "end_value": round(values[-1], 3),
        "mean_value": round(mean(values), 3),
        "n_values": len(values),
    }


def summarize_tail_window(csv_path: str | Path, value_column: str, size: int = 3) -> list[float]:
    rows = load_artifact_csv(csv_path)
    values = [float(row[value_column]) for row in rows if row.get(value_column) not in (None, "")]
    return [round(value, 3) for value in values[-size:]]


def summarize_model_spread(csv_path: str | Path, model_columns: list[str]) -> dict[str, Any]:
    rows = load_artifact_csv(csv_path)
    widest_spread = -1.0
    widest_position = ""
    widest_index = -1
    peak_spreads: dict[str, float] = {}
    for idx, row in enumerate(rows):
        values = [float(row[column]) for column in model_columns if row.get(column) not in (None, "")]
        if len(values) < 2:
            continue
        spread = max(values) - min(values)
        if spread > widest_spread:
            widest_spread = spread
            widest_position = _timestamp_or_index(row, idx)
            widest_index = idx
    for column in model_columns:
        peak_spreads[column] = summarize_peak_and_window(csv_path, column)["peak_value"]
    return {
        "widest_spread": round(widest_spread, 3) if widest_spread >= 0 else None,
        "widest_spread_position": widest_position or None,
        "widest_spread_index": widest_index if widest_index >= 0 else None,
        "model_peak_values": peak_spreads,
    }


def scenario_report_to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# {report['scenario_title']}",
        "",
        "## Scene Goal",
        str(report["scene_goal"]),
        "",
        "## User Input Examples",
    ]
    for item in report["user_input_examples"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Task Recognition", json.dumps(report["task_recognition"], ensure_ascii=False, indent=2), "", "## Workflow Steps"])
    for step in report["workflow_steps"]:
        lines.append(
            f"- {step['step_name']}: {step['tool_name']} | input={step['input']} | output={step['output']} | status={step['status']}"
        )
    lines.extend(["", "## Result Summary", json.dumps(report["result_summary"], ensure_ascii=False, indent=2), "", "## Verification Points"])
    for item in report["verification_points"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Artifacts", json.dumps(report["artifacts"], ensure_ascii=False, indent=2), ""])
    return "\n".join(lines)


def write_scenario_report(output_path: str | Path, report_dict: dict[str, Any]) -> Path:
    target = Path(output_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".json":
        write_json_artifact(target.parent, target.name, report_dict)
    elif target.suffix.lower() == ".md":
        write_text_artifact(target.parent, target.name, scenario_report_to_markdown(report_dict))
    else:
        raise ValueError("Scenario report path must end with .json or .md")
    return target

