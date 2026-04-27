"""Benchmark scenario 6.3.3 via FastMCP."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from experiments.benchmark.common import (
    build_benchmark_run_root,
    call_fastmcp_tool,
    load_artifact_json,
    slice_basin_dataset,
    slice_multistation_dataset,
    summarize_model_spread,
    summarize_peak_and_window,
    write_scenario_report,
)

DEFAULT_START_TIME = "2016-09-28 00:00"
DEFAULT_END_TIME = "2016-09-29 00:00"
MODEL_COLUMNS = ["forecast_xinanjiang", "forecast_gr4j", "forecast_rf", "forecast_lstm"]


def run_scenario(*, output_root: str | None = None, start_time: str = DEFAULT_START_TIME, end_time: str = DEFAULT_END_TIME) -> dict[str, Any]:
    scenario_dir = build_benchmark_run_root("6.3.3-complex-flood", output_root)
    basin_slice = slice_basin_dataset(Path("data") / "basin_001_hourly.csv", start_time, end_time, scenario_dir / "input_slice.csv")
    multistation_slice = slice_multistation_dataset(Path("data") / "rain_15stations_flow.csv", start_time, end_time, scenario_dir / "auxiliary_multistation_slice.csv")
    primary_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(basin_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"basin"}')
    auxiliary_profile = call_fastmcp_tool("dataset_profile_from_paths", dataset_path=str(multistation_slice), output_root=str(scenario_dir / "tool_runs"), options_json='{"profile_type":"multistation"}')
    model_asset_profile = call_fastmcp_tool("model_asset_profile", output_root=str(scenario_dir / "tool_runs"))
    forecast = call_fastmcp_tool("forecast_from_paths", dataset_path=str(basin_slice), output_root=str(scenario_dir / "tool_runs"))
    ensemble = call_fastmcp_tool("ensemble_from_paths", file_path=forecast["artifact_paths"]["forecast"], output_root=str(scenario_dir / "tool_runs"), options_json=json_dumps({"method": "bma", "observation_dataset": str(basin_slice), "observation_column": "streamflow"}))
    correction = call_fastmcp_tool("correction_from_paths", file_path=ensemble["artifact_paths"]["ensemble"], output_root=str(scenario_dir / "tool_runs"), options_json=json_dumps({"observation_dataset": str(basin_slice), "observation_column": "streamflow"}))
    forecast_csv = Path(forecast["artifact_paths"]["forecast"])
    ensemble_csv = Path(ensemble["artifact_paths"]["ensemble"])
    corrected_csv = Path(correction["artifact_paths"]["correction"])
    ensemble_details = load_artifact_json(ensemble["artifact_paths"]["ensemble_details"])
    correction_details = load_artifact_json(correction["artifact_paths"]["correction_details"])
    report = {
        "scenario_id": "6.3.3",
        "scenario_title": "Complex Flood Multi-Tool Forecast Demo",
        "scene_goal": "Show how a complex flood replay can activate multi-model prediction, ensemble synthesis, and error correction through FastMCP tools.",
        "user_input_examples": ["Please replay a typical flood event and produce a 24-hour rolling forecast.", "Please call multiple forecast tools and provide a consolidated flood forecast result."],
        "task_recognition": {"task_type": "complex_flood_forecast", "target_object": "flood inflow process", "time_range": {"start": start_time, "end": end_time}, "output_requirements": ["forecast process line", "peak information", "model difference explanation", "corrected consolidated result"]},
        "workflow_steps": [
            {"step_name": "Primary basin data retrieval", "tool_name": "dataset_retrieval", "input": str(Path("data") / "basin_001_hourly.csv"), "output": str(basin_slice), "status": "completed"},
            {"step_name": "Auxiliary rainfall retrieval", "tool_name": "dataset_retrieval", "input": str(Path("data") / "rain_15stations_flow.csv"), "output": str(multistation_slice), "status": "completed"},
            {"step_name": "Primary dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(basin_slice), "output": primary_profile["artifact_paths"]["dataset_profile"], "status": primary_profile["status"]},
            {"step_name": "Auxiliary dataset loading interface", "tool_name": "dataset_profile_from_paths", "input": str(multistation_slice), "output": auxiliary_profile["artifact_paths"]["dataset_profile"], "status": auxiliary_profile["status"]},
            {"step_name": "Model asset loading interface", "tool_name": "model_asset_profile", "input": "default calibrated/model bundle", "output": model_asset_profile["artifact_paths"]["model_assets_profile"], "status": model_asset_profile["status"]},
            {"step_name": "Multi-model forecast execution", "tool_name": "forecast_from_paths", "input": str(basin_slice), "output": forecast["artifact_paths"]["forecast"], "status": forecast["status"]},
            {"step_name": "Ensemble synthesis", "tool_name": "ensemble_from_paths", "input": forecast["artifact_paths"]["forecast"], "output": ensemble["artifact_paths"]["ensemble"], "status": ensemble["status"]},
            {"step_name": "Error correction", "tool_name": "correction_from_paths", "input": ensemble["artifact_paths"]["ensemble"], "output": correction["artifact_paths"]["correction"], "status": correction["status"]},
        ],
        "tool_calls": [
            {"tool_name": "dataset_profile_from_paths", "operation": primary_profile["operation"], "run_id": primary_profile["run_id"]},
            {"tool_name": "dataset_profile_from_paths", "operation": auxiliary_profile["operation"], "run_id": auxiliary_profile["run_id"]},
            {"tool_name": "model_asset_profile", "operation": model_asset_profile["operation"], "run_id": model_asset_profile["run_id"]},
            {"tool_name": "forecast_from_paths", "operation": forecast["operation"], "run_id": forecast["run_id"]},
            {"tool_name": "ensemble_from_paths", "operation": ensemble["operation"], "run_id": ensemble["run_id"]},
            {"tool_name": "correction_from_paths", "operation": correction["operation"], "run_id": correction["run_id"]},
        ],
        "artifacts": {
            "scenario_dir": str(scenario_dir),
            "basin_slice": str(basin_slice),
            "multistation_slice": str(multistation_slice),
            "primary_dataset_profile": primary_profile["artifact_paths"]["dataset_profile"],
            "auxiliary_dataset_profile": auxiliary_profile["artifact_paths"]["dataset_profile"],
            "model_assets_profile": model_asset_profile["artifact_paths"]["model_assets_profile"],
            "forecast_csv": str(forecast_csv),
            "ensemble_csv": str(ensemble_csv),
            "corrected_csv": str(corrected_csv),
            "forecast_manifest": forecast["output_manifest_path"],
            "ensemble_manifest": ensemble["output_manifest_path"],
            "correction_manifest": correction["output_manifest_path"],
            "ensemble_details": ensemble["artifact_paths"]["ensemble_details"],
            "correction_details": correction["artifact_paths"]["correction_details"],
        },
        "result_summary": {
            "primary_dataset_profile": load_artifact_json(primary_profile["artifact_paths"]["dataset_profile"]),
            "auxiliary_dataset_profile": load_artifact_json(auxiliary_profile["artifact_paths"]["dataset_profile"]),
            "model_asset_profile": load_artifact_json(model_asset_profile["artifact_paths"]["model_assets_profile"]),
            "forecast_peaks": {column: summarize_peak_and_window(forecast_csv, column) for column in MODEL_COLUMNS},
            "ensemble_peak": summarize_peak_and_window(ensemble_csv, "ensemble_forecast"),
            "corrected_peak": summarize_peak_and_window(corrected_csv, "corrected_forecast"),
            "screening": ensemble_details["screening"],
            "selected_model_names": ensemble_details["selected_model_names"],
            "consistency_ratio": ensemble_details["consistency"]["consistency_ratio"],
            "error_metrics": correction_details["error_metrics"],
            "model_difference_summary": summarize_model_spread(forecast_csv, MODEL_COLUMNS),
            "ensemble_weights": ensemble_details["ensemble"]["weights_used"],
            "tool_summaries": {"forecast": forecast["small_summary"], "ensemble": ensemble["small_summary"], "correction": correction["small_summary"]},
        },
        "verification_points": [
            "Benchmark calls FastMCP dataset/model asset tools before forecast execution.",
            "Ensemble and correction nodes are attached through FastMCP tool calls.",
            "Output contains both final consolidated results and intermediate process evidence.",
            "The workflow still stops at forecasting and does not continue into dispatch generation.",
        ],
    }
    report_json = write_scenario_report(scenario_dir / "scenario_report.json", report)
    report_md = write_scenario_report(scenario_dir / "scenario_report.md", report)
    report["artifacts"]["scenario_report_json"] = str(report_json)
    report["artifacts"]["scenario_report_md"] = str(report_md)
    write_scenario_report(report_json, report)
    write_scenario_report(report_md, report)
    return report


def json_dumps(payload: dict[str, Any]) -> str:
    import json
    return json.dumps(payload, ensure_ascii=False)


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

