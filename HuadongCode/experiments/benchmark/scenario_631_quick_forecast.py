"""Benchmark scenario 6.3.1 via FastMCP."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.benchmark.common import (
    build_benchmark_run_root,
    call_fastmcp_tool,
    load_artifact_json,
    slice_basin_dataset,
    summarize_peak_and_window,
    write_scenario_report,
)

DEFAULT_START_TIME = "2015-08-08 18:00"
DEFAULT_END_TIME = "2015-08-09 06:00"
MODEL_COLUMNS = ["forecast_xinanjiang", "forecast_gr4j", "forecast_rf", "forecast_lstm"]


def run_scenario(*, output_root: str | None = None, start_time: str = DEFAULT_START_TIME, end_time: str = DEFAULT_END_TIME) -> dict[str, Any]:
    scenario_dir = build_benchmark_run_root("6.3.1-quick-forecast", output_root)
    input_slice = slice_basin_dataset(Path("data") / "basin_001_hourly.csv", start_time, end_time, scenario_dir / "input_slice.csv")
    dataset_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(input_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"basin"}')
    model_asset_profile = call_fastmcp_tool("model_asset_profile", output_root=str(scenario_dir / "tool_runs"))
    forecast = call_fastmcp_tool("forecast_from_paths", dataset_path=str(input_slice), output_root=str(scenario_dir / "tool_runs"))
    forecast_csv = Path(forecast["artifact_paths"]["forecast"])
    metrics = load_artifact_json(forecast["artifact_paths"]["forecast_metrics"])["metrics"]
    report = {
        "scenario_id": "6.3.1",
        "scenario_title": "Quick Forecast Service Demo",
        "scene_goal": "Show that the system can recognize a simple forecast request and complete the shortest forecast workflow through FastMCP.",
        "user_input_examples": ["Please run a quick inflow forecast.", "Please run a quick forecast based on the latest rainfall and streamflow."],
        "task_recognition": {"task_type": "quick_forecast", "target_object": "basin inflow", "time_range": {"start": start_time, "end": end_time}, "output_requirements": ["forecast series", "brief textual summary"]},
        "workflow_steps": [
            {"step_name": "Input slicing", "tool_name": "dataset_retrieval", "input": str(Path("data") / "basin_001_hourly.csv"), "output": str(input_slice), "status": "completed"},
            {"step_name": "Dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(input_slice), "output": dataset_profile["artifact_paths"]["dataset_profile"], "status": dataset_profile["status"]},
            {"step_name": "Model asset loading interface", "tool_name": "model_asset_profile", "input": "default calibrated/model bundle", "output": model_asset_profile["artifact_paths"]["model_assets_profile"], "status": model_asset_profile["status"]},
            {"step_name": "Forecast execution", "tool_name": "forecast_from_paths", "input": str(input_slice), "output": str(forecast_csv), "status": forecast["status"]},
        ],
        "tool_calls": [
            {"tool_name": "dataset_profile_from_paths", "operation": dataset_profile["operation"], "run_id": dataset_profile["run_id"]},
            {"tool_name": "model_asset_profile", "operation": model_asset_profile["operation"], "run_id": model_asset_profile["run_id"]},
            {"tool_name": "forecast_from_paths", "operation": forecast["operation"], "run_id": forecast["run_id"]},
        ],
        "artifacts": {
            "scenario_dir": str(scenario_dir),
            "input_slice": str(input_slice),
            "dataset_profile": dataset_profile["artifact_paths"]["dataset_profile"],
            "model_assets_profile": model_asset_profile["artifact_paths"]["model_assets_profile"],
            "forecast_csv": str(forecast_csv),
            "forecast_manifest": forecast["output_manifest_path"],
            "forecast_metrics": forecast["artifact_paths"]["forecast_metrics"],
        },
        "result_summary": {
            "dataset_profile": load_artifact_json(dataset_profile["artifact_paths"]["dataset_profile"]),
            "model_asset_profile": load_artifact_json(model_asset_profile["artifact_paths"]["model_assets_profile"]),
            "input_rows": summarize_peak_and_window(input_slice, "streamflow")["n_values"],
            "model_metrics": metrics,
            "model_peaks": {column: summarize_peak_and_window(forecast_csv, column) for column in MODEL_COLUMNS},
            "observed_window": summarize_peak_and_window(forecast_csv, "observed"),
            "tool_summary": forecast["small_summary"],
        },
        "verification_points": [
            "Task type can be resolved as forecast instead of query-only QA.",
            "FastMCP dataset/model asset tools run before forecast execution.",
            "Single forecast tool can complete the business minimum loop.",
            "Result output remains normalized and artifact-based.",
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
    parser.add_argument("--end-time", default=DEFAULT_END_TIME)
    args = parser.parse_args()
    report = run_scenario(output_root=args.output_root, start_time=args.start_time, end_time=args.end_time)
    print(report["artifacts"]["scenario_report_json"])


if __name__ == "__main__":
    main()

