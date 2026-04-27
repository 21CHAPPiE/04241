"""Risk tool module."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.risk import run_risk_pipeline
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, write_json_artifact, write_text_artifact
from app.tools.common import finalize_and_respond, resolve_small_summary
from app.tools.helpers import create_run, resolve_inputs


def run_risk_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("file_path") or inputs.get("dataset_path")
    run_id, run_dir = create_run("risk", output_root)
    manifest = create_manifest(operation="risk", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    thresholds = dict(options.get("thresholds", {"flood": 300.0, "severe": 500.0})) if options else {"flood": 300.0, "severe": 500.0}
    result = run_risk_pipeline(
        predictions_path=source_path,
        model_columns=list(options.get("model_columns", ["corrected_forecast"])) if options else ["corrected_forecast"],
        thresholds=thresholds,
        artifact_dir=run_dir,
    )
    risk_path = write_json_artifact(run_dir, "risk.json", result["risk"])
    add_manifest_artifact(manifest, name="risk", path=risk_path, kind="json")
    summary_path = write_text_artifact(run_dir, "summary.txt", resolve_small_summary(result["summary_text"]))
    add_manifest_artifact(manifest, name="summary", path=summary_path, kind="text")
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="risk", summary=result["summary_text"])


def setup_risk_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="risk_from_paths")
    def risk_from_paths_tool(
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
        return run_risk_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
