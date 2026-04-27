"""Warning tool module."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.warning import run_warning_pipeline
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, write_json_artifact, write_text_artifact
from app.tools.common import finalize_and_respond, resolve_small_summary
from app.tools.helpers import create_run, resolve_inputs


def run_warning_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("file_path") or inputs.get("dataset_path")
    run_id, run_dir = create_run("warning", output_root)
    manifest = create_manifest(operation="warning", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    result = run_warning_pipeline(
        forecast_path=source_path,
        forecast_column=str(options.get("forecast_column", "corrected_forecast")) if options else "corrected_forecast",
        warning_threshold=float(options.get("warning_threshold", 300.0)) if options else 300.0,
        lead_time_hours=int(options.get("lead_time_hours", 24)) if options and options.get("lead_time_hours") is not None else None,
        artifact_dir=run_dir,
    )
    warning_path = write_json_artifact(run_dir, "warning.json", {"flood_warning": result["flood_warning"], "drought_warning": result["drought_warning"]})
    add_manifest_artifact(manifest, name="warning", path=warning_path, kind="json")
    summary_path = write_text_artifact(run_dir, "summary.txt", resolve_small_summary(result["summary_text"]))
    add_manifest_artifact(manifest, name="summary", path=summary_path, kind="text")
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="warning", summary=result["summary_text"])


def setup_warning_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="warning_from_paths")
    def warning_from_paths_tool(
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
        return run_warning_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
