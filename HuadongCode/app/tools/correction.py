"""Correction tool module."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.error_analysis import run_error_analysis_pipeline
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, resolve_dataset_path, write_csv_artifact
from app.tools.common import finalize_and_respond
from app.tools.helpers import (
    create_run,
    detect_time_column,
    read_csv_rows,
    read_numeric_column,
    read_text_column,
    resolve_inputs,
    write_summary_artifacts,
)


def run_correction_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    ensemble_path = inputs.get("file_path") or inputs.get("dataset_path")
    observation_path = str(resolve_dataset_path(str(options["observation_dataset"]))) if options and options.get("observation_dataset") else None
    observation_column = str(options.get("observation_column", "streamflow")) if options else "streamflow"
    run_id, run_dir = create_run("correction", output_root)
    manifest = create_manifest(operation="correction", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    ensemble_rows = read_csv_rows(ensemble_path)
    ensemble_values = [float(row["ensemble_forecast"]) for row in ensemble_rows if row.get("ensemble_forecast") not in (None, "")]
    ensemble_time_column = detect_time_column(ensemble_path)
    ensemble_timestamps = read_text_column(ensemble_path, ensemble_time_column) if ensemble_time_column else []
    if observation_path is None:
        raise ValueError("correction requires options.observation_dataset pointing to the observation CSV")
    observations = read_numeric_column(observation_path, observation_column)
    observation_time_column = detect_time_column(observation_path)
    observation_timestamps = read_text_column(observation_path, observation_time_column) if observation_time_column else []
    min_len = min(len(ensemble_values), len(observations))
    pred = ensemble_values[:min_len]
    obs = observations[:min_len]
    analysis = run_error_analysis_pipeline(predictions=pred, observations=obs, artifact_dir=run_dir)
    bias = analysis["error_metrics"]["Bias"] or 0.0
    corrected = [float(value - bias) for value in pred]
    corrected_rows = []
    for idx in range(min_len):
        row: dict[str, Any] = {
            "index": idx,
            "ensemble_forecast": pred[idx],
            "observed": obs[idx],
            "corrected_forecast": corrected[idx],
        }
        if idx < len(ensemble_timestamps):
            row["timestamp"] = ensemble_timestamps[idx]
        elif idx < len(observation_timestamps):
            row["timestamp"] = observation_timestamps[idx]
        corrected_rows.append(row)
    fieldnames = ["index"]
    if corrected_rows and "timestamp" in corrected_rows[0]:
        fieldnames.append("timestamp")
    fieldnames.extend(["ensemble_forecast", "observed", "corrected_forecast"])
    corrected_path = write_csv_artifact(run_dir, "corrected.csv", corrected_rows, fieldnames)
    add_manifest_artifact(manifest, name="correction", path=corrected_path, kind="csv")
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text=analysis["summary_text"],
        payload_name="correction_details.json",
        payload={
            "error_metrics": analysis["error_metrics"],
            "anomaly_info": analysis["anomaly_info"],
            "correction_summary": analysis["correction_summary"],
        },
    )
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="correction", summary=analysis["summary_text"])


def setup_correction_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="correction_from_paths")
    def correction_from_paths_tool(
        dataset_path: str | None = None,
        file_path: str | None = None,
        output_root: str | None = None,
        options_json: str | None = None,
    ) -> dict[str, Any]:
        import json

        if options_json is None or not options_json.strip():
            options: dict[str, Any] = {}
        else:
            parsed = json.loads(options_json)
            if not isinstance(parsed, dict):
                raise ValueError("options_json must decode to a JSON object")
            options = parsed
        return run_correction_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
