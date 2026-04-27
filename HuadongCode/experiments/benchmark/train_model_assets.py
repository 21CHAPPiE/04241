"""Train model bundle via FastMCP benchmark path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.benchmark.common import build_benchmark_run_root, call_fastmcp_tool, load_artifact_json, write_scenario_report


def run_training(*, dataset_path: str = "basin_001_hourly.csv", bundle_path: str = "data/calibrated_parameters/forecast_model_bundle.pt", output_root: str | None = None) -> dict:
    scenario_dir = build_benchmark_run_root("training-assets", output_root)
    result = call_fastmcp_tool(
        "train_model_bundle_from_paths",
        dataset_path=dataset_path,
        output_root=str(scenario_dir / "tool_runs"),
        options_json=json.dumps(
            {
                "bundle_path": str(Path(bundle_path).resolve()),
                "max_rows": 12000,
                "sequence_length": 8,
                "lstm_epochs": 6,
            },
            ensure_ascii=False,
        ),
    )
    details = load_artifact_json(result["artifact_paths"]["training_bundle_details"])
    report = {
        "scenario_id": "training-assets",
        "scenario_title": "Forecast Asset Training",
        "scene_goal": "Train learned forecast assets and save them together with hydrological parameter assets through FastMCP.",
        "user_input_examples": ["Train the forecast model assets and save them with the hydrological parameters."],
        "task_recognition": {"task_type": "asset_training", "target_object": "forecast model bundle", "time_range": None, "output_requirements": ["serialized model bundle", "training summary"]},
        "workflow_steps": [{"step_name": "Training bundle generation", "tool_name": "train_model_bundle_from_paths", "input": dataset_path, "output": bundle_path, "status": result["status"]}],
        "tool_calls": [{"tool_name": "train_model_bundle_from_paths", "operation": result["operation"], "run_id": result["run_id"]}],
        "artifacts": {"bundle_path": bundle_path, "training_summary": result["artifact_paths"]["training_bundle_summary"]},
        "result_summary": details,
        "verification_points": [
            "Hydrological parameters and learned assets are saved in one serialized bundle.",
            "RF and LSTM assets are available for forecast loading.",
            "The bundle remains compatible with fallback CSV hydrological parameters.",
        ],
    }
    report_json = write_scenario_report(scenario_dir / "training_report.json", report)
    report_md = write_scenario_report(scenario_dir / "training_report.md", report)
    report["artifacts"]["training_report_json"] = str(report_json)
    report["artifacts"]["training_report_md"] = str(report_md)
    write_scenario_report(report_json, report)
    write_scenario_report(report_md, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-path", default="basin_001_hourly.csv")
    parser.add_argument("--bundle-path", default="data/calibrated_parameters/forecast_model_bundle.pt")
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()
    report = run_training(dataset_path=args.dataset_path, bundle_path=args.bundle_path, output_root=args.output_root)
    print(report["artifacts"]["training_report_json"])


if __name__ == "__main__":
    main()
