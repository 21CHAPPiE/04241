"""Forecast tool module."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.forecast import run_forecast_pipeline
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, write_csv_artifact
from app.tools.common import finalize_and_respond
from app.tools.helpers import create_run, resolve_inputs, write_summary_artifacts


def _rows_from_forecast_frame(frame: Any) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": timestamp,
            "rainfall": frame.rainfall[idx],
            "pet": frame.pet[idx],
            "observed": frame.observed[idx],
            "forecast_xinanjiang": frame.xinanjiang[idx],
            "forecast_gr4j": frame.gr4j[idx],
            "forecast_rf": frame.rf[idx],
            "forecast_lstm": frame.lstm[idx],
        }
        for idx, timestamp in enumerate(frame.timestamps)
    ]


def run_forecast_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("forecast", output_root)
    manifest = create_manifest(operation="forecast", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    result = run_forecast_pipeline(dataset_path=source_path, artifact_dir=run_dir)
    forecast_path = write_csv_artifact(
        run_dir,
        "forecast.csv",
        _rows_from_forecast_frame(result["frame"]),
        [
            "timestamp",
            "rainfall",
            "pet",
            "observed",
            "forecast_xinanjiang",
            "forecast_gr4j",
            "forecast_rf",
            "forecast_lstm",
        ],
    )
    add_manifest_artifact(manifest, name="forecast", path=forecast_path, kind="csv")
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text=result["summary_text"],
        payload_name="forecast_metrics.json",
        payload={"metrics": result["metrics"]},
    )
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="forecast", summary=result["summary_text"])


def setup_forecast_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="forecast_from_paths")
    def forecast_from_paths_tool(
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
        return run_forecast_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
