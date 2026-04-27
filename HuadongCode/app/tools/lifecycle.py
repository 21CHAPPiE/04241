"""Lifecycle-oriented tool modules."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.lifecycle import (
    run_calibration_pipeline,
    run_hpo_pipeline,
    run_training_pipeline,
    save_training_model,
)
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, write_json_artifact, write_text_artifact
from app.tools.common import finalize_and_respond
from app.tools.helpers import create_run, resolve_inputs, write_summary_artifacts


def run_training_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("training", output_root)
    manifest = create_manifest(operation="training", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    result = run_training_pipeline(dataset_path=source_path, artifact_dir=run_dir)
    model_path = save_training_model(run_dir / "model.pt", result["model_state"])
    add_manifest_artifact(manifest, name="model", path=model_path, kind="model")
    write_summary_artifacts(run_dir=run_dir, manifest=manifest, summary_text=result["summary_text"], payload_name="training.json", payload=result["model_state"])
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="training", summary=result["summary_text"])


def run_calibration_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("calibration", output_root)
    manifest = create_manifest(operation="calibration", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    result = run_calibration_pipeline(dataset_path=source_path, artifact_dir=run_dir)
    write_summary_artifacts(run_dir=run_dir, manifest=manifest, summary_text=result["summary_text"], payload_name="calibration.json", payload=result["parameters"])
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="calibration", summary=result["summary_text"])


def run_hpo_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("hpo", output_root)
    manifest = create_manifest(operation="hpo", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    result = run_hpo_pipeline(dataset_path=source_path, artifact_dir=run_dir)
    write_summary_artifacts(run_dir=run_dir, manifest=manifest, summary_text=result["summary_text"], payload_name="hpo.json", payload=result["best_result"])
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="hpo", summary=result["summary_text"])


def run_lifecycle_smoke_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("lifecycle-smoke", output_root)
    manifest = create_manifest(operation="lifecycle-smoke", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    training = run_training_pipeline(dataset_path=source_path, artifact_dir=run_dir, artifact_prefix="training")
    model_path = save_training_model(run_dir / "model.pt", training["model_state"])
    add_manifest_artifact(manifest, name="model", path=model_path, kind="model")
    calibration = run_calibration_pipeline(dataset_path=source_path, artifact_dir=run_dir, artifact_prefix="calibration")
    calibration_path = write_json_artifact(run_dir, "calibration.json", calibration["parameters"])
    add_manifest_artifact(manifest, name="calibration", path=calibration_path, kind="json")
    hpo = run_hpo_pipeline(dataset_path=source_path, artifact_dir=run_dir, artifact_prefix="hpo")
    hpo_path = write_json_artifact(run_dir, "hpo.json", hpo["best_result"])
    add_manifest_artifact(manifest, name="hpo", path=hpo_path, kind="json")
    summary = "Lifecycle smoke completed for training, calibration, and HPO."
    summary_path = write_text_artifact(run_dir, "summary.txt", summary)
    add_manifest_artifact(manifest, name="summary", path=summary_path, kind="text")
    return finalize_and_respond(manifest=manifest, run_dir=run_dir, run_id=run_id, operation="lifecycle-smoke", summary=summary)


def setup_lifecycle_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="training_from_paths")
    def training_from_paths_tool(
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
        return run_training_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )

    @mcp_server.tool(name="calibration_from_paths")
    def calibration_from_paths_tool(
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
        return run_calibration_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )

    @mcp_server.tool(name="hpo_from_paths")
    def hpo_from_paths_tool(
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
        return run_hpo_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )

    @mcp_server.tool(name="lifecycle_smoke_from_paths")
    def lifecycle_smoke_from_paths_tool(
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
        return run_lifecycle_smoke_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
