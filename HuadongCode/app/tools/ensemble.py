"""Ensemble tool module."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.ensemble import run_ensemble_pipeline
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, resolve_dataset_path, write_csv_artifact
from app.tools.common import finalize_and_respond
from app.tools.helpers import (
    create_run,
    detect_time_column,
    read_numeric_column,
    read_text_column,
    resolve_inputs,
    write_summary_artifacts,
)


def run_ensemble_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("file_path") or inputs.get("dataset_path")
    run_id, run_dir = create_run("ensemble", output_root)
    manifest = create_manifest(operation="ensemble", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    columns = (
        list(
            options.get(
                "model_columns",
                [
                    "forecast_xinanjiang",
                    "forecast_gr4j",
                    "forecast_rf",
                    "forecast_lstm",
                ],
            )
        )
        if options
        else [
            "forecast_xinanjiang",
            "forecast_gr4j",
            "forecast_rf",
            "forecast_lstm",
        ]
    )
    result = run_ensemble_pipeline(
        predictions_path=source_path,
        model_columns=columns,
        observations=(
            read_numeric_column(
                str(resolve_dataset_path(str(options["observation_dataset"]))),
                str(options.get("observation_column", "streamflow")),
            )
            if options and options.get("observation_dataset")
            else None
        ),
        method=str(options.get("method", "weighted_mean")) if options else "weighted_mean",
        weights=list(options["weights"]) if options and options.get("weights") else None,
        initial_weights=list(options["initial_weights"]) if options and options.get("initial_weights") else None,
        window_size=int(options.get("window_size", 30)) if options else 30,
        rmse_threshold=float(options["rmse_threshold"]) if options and options.get("rmse_threshold") is not None else None,
        nse_threshold=float(options["nse_threshold"]) if options and options.get("nse_threshold") is not None else None,
        bias_threshold=float(options["bias_threshold"]) if options and options.get("bias_threshold") is not None else None,
        artifact_dir=run_dir,
    )
    time_column = detect_time_column(source_path)
    timestamps = read_text_column(source_path, time_column) if time_column else []
    rows = []
    for idx, value in enumerate(result["ensemble"]["ensemble_forecast"]):
        row: dict[str, Any] = {"index": idx, "ensemble_forecast": value}
        if idx < len(timestamps):
            row["timestamp"] = timestamps[idx]
        rows.append(row)
    fieldnames = ["index"]
    if timestamps:
        fieldnames.append("timestamp")
    fieldnames.append("ensemble_forecast")
    ensemble_path = write_csv_artifact(run_dir, "ensemble.csv", rows, fieldnames)
    add_manifest_artifact(manifest, name="ensemble", path=ensemble_path, kind="csv")
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text=result["summary_text"],
        payload_name="ensemble_details.json",
        payload={
            "selected_model_names": result["selected_model_names"],
            "screening": result["screening"],
            "consistency": result["consistency"],
            "ensemble": result["ensemble"],
        },
    )
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="ensemble", summary=result["summary_text"])


def setup_ensemble_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="ensemble_from_paths")
    def ensemble_from_paths_tool(
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
        return run_ensemble_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
