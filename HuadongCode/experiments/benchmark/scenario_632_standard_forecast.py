"""Benchmark scenario 6.3.2 via FastMCP."""

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

DEFAULT_START_TIME = "2016-09-27 18:00"
DEFAULT_END_TIME = "2016-09-28 18:00"
MODEL_COLUMNS = ["forecast_xinanjiang", "forecast_gr4j", "forecast_rf", "forecast_lstm"]


def run_scenario(*, output_root: str | None = None, start_time: str = DEFAULT_START_TIME, end_time: str = DEFAULT_END_TIME) -> dict[str, Any]:
    scenario_dir = build_benchmark_run_root("6.3.2-standard-forecast", output_root)
    input_slice = slice_basin_dataset(Path("data") / "basin_001_hourly.csv", start_time, end_time, scenario_dir / "input_slice.csv")
    dataset_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(input_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"basin"}')
    model_asset_profile = call_fastmcp_tool("model_asset_profile", output_root=str(scenario_dir / "tool_runs"))
    analysis = call_fastmcp_tool("data_analysis_from_paths", dataset_path=str(input_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"column":"streamflow"}')
    forecast = call_fastmcp_tool("forecast_from_paths", dataset_path=str(input_slice), output_root=str(scenario_dir / "tool_runs"))
    forecast_csv = Path(forecast["artifact_paths"]["forecast"])
    analysis_json = load_artifact_json(analysis["artifact_paths"]["analysis"])
    metrics = load_artifact_json(forecast["artifact_paths"]["forecast_metrics"])["metrics"]
    report = {
        "scenario_id": "6.3.2",
        "scenario_title": "Standard Forecast Workflow Demo",
        "scene_goal": "Show that the system can organize a standard forecast workflow with FastMCP tools.",
        "user_input_examples": ["Please generate a standard 24-hour inflow forecast based on the current rainfall and streamflow.", "Please provide the peak value and a brief summary for the next-day forecast."],
        "task_recognition": {"task_type": "standard_forecast", "target_object": "basin inflow", "time_range": {"start": start_time, "end": end_time}, "output_requirements": ["forecast series", "peak summary", "business-readable description"]},
        "workflow_steps": [
            {"step_name": "Input slicing", "tool_name": "dataset_retrieval", "input": str(Path("data") / "basin_001_hourly.csv"), "output": str(input_slice), "status": "completed"},
            {"step_name": "Dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(input_slice), "output": dataset_profile["artifact_paths"]["dataset_profile"], "status": dataset_profile["status"]},
            {"step_name": "Model asset loading interface", "tool_name": "model_asset_profile", "input": "default calibrated/model bundle", "output": model_asset_profile["artifact_paths"]["model_assets_profile"], "status": model_asset_profile["status"]},
            {"step_name": "Data analysis", "tool_name": "data_analysis_from_paths", "input": str(input_slice), "output": analysis["artifact_paths"]["analysis"], "status": analysis["status"]},
            {"step_name": "Forecast execution", "tool_name": "forecast_from_paths", "input": str(input_slice), "output": forecast["artifact_paths"]["forecast"], "status": forecast["status"]},
            {"step_name": "Business result packaging", "tool_name": "result_summary", "input": forecast["artifact_paths"]["forecast"], "output": str(scenario_dir / "scenario_report.json"), "status": "completed"},
        ],
        "tool_calls": [
            {"tool_name": "dataset_profile_from_paths", "operation": dataset_profile["operation"], "run_id": dataset_profile["run_id"]},
            {"tool_name": "model_asset_profile", "operation": model_asset_profile["operation"], "run_id": model_asset_profile["run_id"]},
            {"tool_name": "data_analysis_from_paths", "operation": analysis["operation"], "run_id": analysis["run_id"]},
            {"tool_name": "forecast_from_paths", "operation": forecast["operation"], "run_id": forecast["run_id"]},
        ],
        "artifacts": {
            "scenario_dir": str(scenario_dir),
            "input_slice": str(input_slice),
            "dataset_profile": dataset_profile["artifact_paths"]["dataset_profile"],
            "model_assets_profile": model_asset_profile["artifact_paths"]["model_assets_profile"],
            "analysis_json": analysis["artifact_paths"]["analysis"],
            "analysis_manifest": analysis["output_manifest_path"],
            "forecast_csv": forecast["artifact_paths"]["forecast"],
            "forecast_manifest": forecast["output_manifest_path"],
            "forecast_metrics": forecast["artifact_paths"]["forecast_metrics"],
        },
        "result_summary": {
            "dataset_profile": load_artifact_json(dataset_profile["artifact_paths"]["dataset_profile"]),
            "model_asset_profile": load_artifact_json(model_asset_profile["artifact_paths"]["model_assets_profile"]),
            "trend_analysis": analysis_json["trend"],
            "cycle_analysis": analysis_json["cycle"],
            "mutation_analysis": analysis_json["mutation"],
            "observed_window": summarize_peak_and_window(forecast_csv, "observed"),
            "model_peaks": {column: summarize_peak_and_window(forecast_csv, column) for column in MODEL_COLUMNS},
            "model_metrics": metrics,
            "peak_focus": max((summarize_peak_and_window(forecast_csv, column) for column in MODEL_COLUMNS), key=lambda item: item["peak_value"] or float("-inf")),
            "tool_summaries": {"analysis": analysis["small_summary"], "forecast": forecast["small_summary"]},
        },
        "verification_points": [
            "FastMCP dataset/model asset tools run before analysis and forecast.",
            "The workflow contains a separate data-analysis step before forecasting.",
            "The output is organized into peak and summary fields instead of raw numbers only.",
            "The workflow remains in the forecast domain and does not enter dispatch generation.",
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

