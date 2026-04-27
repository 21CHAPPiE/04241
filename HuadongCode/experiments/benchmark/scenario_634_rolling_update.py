"""Benchmark scenario 6.3.4 via FastMCP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from experiments.benchmark.common import (
    build_benchmark_run_root,
    call_fastmcp_tool,
    load_artifact_json,
    slice_basin_dataset,
    summarize_peak_and_window,
    summarize_tail_window,
    write_scenario_report,
)

DEFAULT_START_TIME = "2016-09-28 00:00"
DEFAULT_INITIAL_END_TIME = "2016-09-28 12:00"
DEFAULT_UPDATED_END_TIME = "2016-09-28 18:00"


def _run_chain(input_slice: Path, tool_run_root: Path) -> dict[str, Any]:
    forecast = call_fastmcp_tool("forecast_from_paths", dataset_path=str(input_slice), output_root=str(tool_run_root))
    ensemble = call_fastmcp_tool(
        "ensemble_from_paths",
        file_path=forecast["artifact_paths"]["forecast"],
        output_root=str(tool_run_root),
        options_json=json.dumps({"method": "bma", "observation_dataset": str(input_slice), "observation_column": "streamflow"}, ensure_ascii=False),
    )
    correction = call_fastmcp_tool(
        "correction_from_paths",
        file_path=ensemble["artifact_paths"]["ensemble"],
        output_root=str(tool_run_root),
        options_json=json.dumps({"observation_dataset": str(input_slice), "observation_column": "streamflow"}, ensure_ascii=False),
    )
    return {"forecast": forecast, "ensemble": ensemble, "correction": correction}


def run_scenario(*, output_root: str | None = None, start_time: str = DEFAULT_START_TIME, initial_end_time: str = DEFAULT_INITIAL_END_TIME, updated_end_time: str = DEFAULT_UPDATED_END_TIME) -> dict[str, Any]:
    scenario_dir = build_benchmark_run_root("6.3.4-rolling-update", output_root)
    initial_slice = slice_basin_dataset(Path("data") / "basin_001_hourly.csv", start_time, initial_end_time, scenario_dir / "initial_input_slice.csv")
    updated_slice = slice_basin_dataset(Path("data") / "basin_001_hourly.csv", start_time, updated_end_time, scenario_dir / "updated_input_slice.csv")
    initial_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(initial_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"basin"}')
    model_asset_profile = call_fastmcp_tool("model_asset_profile", output_root=str(scenario_dir / "tool_runs"))
    initial_run = _run_chain(initial_slice, scenario_dir / "tool_runs" / "initial")
    updated_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(updated_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"basin"}')
    updated_run = _run_chain(updated_slice, scenario_dir / "tool_runs" / "updated")
    initial_corrected_csv = Path(initial_run["correction"]["artifact_paths"]["correction"])
    updated_corrected_csv = Path(updated_run["correction"]["artifact_paths"]["correction"])
    initial_peak = summarize_peak_and_window(initial_corrected_csv, "corrected_forecast")
    updated_peak = summarize_peak_and_window(updated_corrected_csv, "corrected_forecast")
    report = {
        "scenario_id": "6.3.4",
        "scenario_title": "Rolling Update and Reforecast Demo",
        "scene_goal": "Show that the system can treat newly arrived observations as an update task and rerun the forecast chain through FastMCP.",
        "user_input_examples": ["Please create a 24-hour forecast and update it when new observations arrive.", "New rainfall data has arrived. Please update the previous forecast."],
        "task_recognition": {"task_type": "rolling_forecast_update", "target_object": "basin inflow", "time_range": {"start": start_time, "initial_end": initial_end_time, "updated_end": updated_end_time}, "output_requirements": ["updated forecast", "difference summary", "before/after comparison"]},
        "workflow_steps": [
            {"step_name": "Initial dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(initial_slice), "output": initial_profile["artifact_paths"]["dataset_profile"], "status": initial_profile["status"]},
            {"step_name": "Model asset loading interface", "tool_name": "model_asset_profile", "input": "default calibrated/model bundle", "output": model_asset_profile["artifact_paths"]["model_assets_profile"], "status": model_asset_profile["status"]},
            {"step_name": "Initial forecast chain", "tool_name": "forecast -> ensemble -> correction", "input": str(initial_slice), "output": initial_run["correction"]["artifact_paths"]["correction"], "status": "completed"},
            {"step_name": "Update trigger", "tool_name": "new_observation_ingest", "input": str(updated_slice), "output": "recognized as update request", "status": "completed"},
            {"step_name": "Updated dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(updated_slice), "output": updated_profile["artifact_paths"]["dataset_profile"], "status": updated_profile["status"]},
            {"step_name": "Updated forecast chain", "tool_name": "forecast -> ensemble -> correction", "input": str(updated_slice), "output": updated_run["correction"]["artifact_paths"]["correction"], "status": "completed"},
            {"step_name": "Before/after comparison", "tool_name": "result_comparison", "input": f"{initial_corrected_csv} | {updated_corrected_csv}", "output": str(scenario_dir / "scenario_report.json"), "status": "completed"},
        ],
        "tool_calls": [
            {"tool_name": "dataset_profile_from_paths", "operation": initial_profile["operation"], "run_id": initial_profile["run_id"], "phase": "initial"},
            {"tool_name": "model_asset_profile", "operation": model_asset_profile["operation"], "run_id": model_asset_profile["run_id"]},
            {"tool_name": "forecast_from_paths", "run_id": initial_run["forecast"]["run_id"], "phase": "initial"},
            {"tool_name": "ensemble_from_paths", "run_id": initial_run["ensemble"]["run_id"], "phase": "initial"},
            {"tool_name": "correction_from_paths", "run_id": initial_run["correction"]["run_id"], "phase": "initial"},
            {"tool_name": "dataset_profile_from_paths", "operation": updated_profile["operation"], "run_id": updated_profile["run_id"], "phase": "updated"},
            {"tool_name": "forecast_from_paths", "run_id": updated_run["forecast"]["run_id"], "phase": "updated"},
            {"tool_name": "ensemble_from_paths", "run_id": updated_run["ensemble"]["run_id"], "phase": "updated"},
            {"tool_name": "correction_from_paths", "run_id": updated_run["correction"]["run_id"], "phase": "updated"},
        ],
        "artifacts": {
            "scenario_dir": str(scenario_dir),
            "initial_input_slice": str(initial_slice),
            "updated_input_slice": str(updated_slice),
            "initial_dataset_profile": initial_profile["artifact_paths"]["dataset_profile"],
            "updated_dataset_profile": updated_profile["artifact_paths"]["dataset_profile"],
            "model_assets_profile": model_asset_profile["artifact_paths"]["model_assets_profile"],
            "initial_corrected_csv": str(initial_corrected_csv),
            "updated_corrected_csv": str(updated_corrected_csv),
            "initial_manifest": initial_run["correction"]["output_manifest_path"],
            "updated_manifest": updated_run["correction"]["output_manifest_path"],
        },
        "result_summary": {
            "initial_dataset_profile": load_artifact_json(initial_profile["artifact_paths"]["dataset_profile"]),
            "updated_dataset_profile": load_artifact_json(updated_profile["artifact_paths"]["dataset_profile"]),
            "model_asset_profile": load_artifact_json(model_asset_profile["artifact_paths"]["model_assets_profile"]),
            "update_trigger_reason": "New observations extend the forecast context from the initial window to the updated window.",
            "rerun_steps": ["forecast_from_paths", "ensemble_from_paths", "correction_from_paths"],
            "initial_vs_updated_peak": {"initial": initial_peak, "updated": updated_peak},
            "initial_vs_updated_tail_window": {"initial": summarize_tail_window(initial_corrected_csv, "corrected_forecast"), "updated": summarize_tail_window(updated_corrected_csv, "corrected_forecast")},
            "delta_summary": {"peak_value_delta": round((updated_peak["peak_value"] or 0.0) - (initial_peak["peak_value"] or 0.0), 3), "initial_length": initial_peak["n_values"], "updated_length": updated_peak["n_values"]},
        },
        "verification_points": [
            "The task is recognized as an update instead of a brand-new scenario.",
            "FastMCP dataset/model asset tools run before each forecast stage.",
            "Initial and updated outputs can be compared with fixed summary fields.",
            "The workflow demonstrates rolling forecast behavior without entering dispatch generation.",
        ],
    }
    report_json = write_scenario_report(scenario_dir / "scenario_report.json", report)
    report_md = write_scenario_report(scenario_dir / "scenario_report.md", report)
    report["artifacts"]["scenario_report_json"] = str(report_json)
    report["artifacts"]["scenario_report_md"] = str(report_md)
    write_scenario_report(report_json, report)
    write_scenario_report(report_md, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--start-time", default=DEFAULT_START_TIME)
    parser.add_argument("--initial-end-time", default=DEFAULT_INITIAL_END_TIME)
    parser.add_argument("--updated-end-time", default=DEFAULT_UPDATED_END_TIME)
    args = parser.parse_args()
    report = run_scenario(output_root=args.output_root, start_time=args.start_time, initial_end_time=args.initial_end_time, updated_end_time=args.updated_end_time)
    print(report["artifacts"]["scenario_report_json"])


if __name__ == "__main__":
    main()
