"""Dataset/model-asset inspection tools for FastMCP workflows."""

from __future__ import annotations

from typing import Any, Mapping

from fastmcp import FastMCP

from app.core.data_loading import describe_dataset, load_basin_dataset, load_multistation_dataset
from app.core.model_assets import describe_model_asset_bundle, load_model_asset_bundle
from app.core.trained_models import train_forecast_model_bundle
from app.domain import ToolExecutionResult
from app.io import add_manifest_artifact, create_manifest, write_json_artifact
from app.tools.common import finalize_and_respond
from app.tools.helpers import create_run, resolve_inputs, write_summary_artifacts


def run_dataset_profile_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    profile_type = str(options.get("profile_type", "basin")) if options else "basin"
    run_id, run_dir = create_run("dataset-profile", output_root)
    manifest = create_manifest(operation="dataset-profile", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    if profile_type == "multistation":
        profile = describe_dataset(load_multistation_dataset(source_path))
    else:
        profile = describe_dataset(load_basin_dataset(source_path))
    profile_path = write_json_artifact(run_dir, "dataset_profile.json", profile)
    add_manifest_artifact(manifest, name="dataset_profile", path=profile_path, kind="json")
    summary = f"Loaded dataset profile for {profile['schema_name']} with {profile['n_rows']} rows."
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text=summary,
        payload_name="dataset_profile_summary.json",
        payload=profile,
    )
    return finalize_and_respond(
        manifest=manifest,
        run_dir=run_dir,
        run_id=run_id,
        operation="dataset-profile",
        summary=summary,
    )


def run_model_asset_profile(
    *,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    run_id, run_dir = create_run("model-asset-profile", output_root)
    manifest = create_manifest(operation="model-asset-profile", run_id=run_id, run_dir=run_dir, inputs={}, options=options)
    bundle_path = str(options.get("bundle_path")) if options and options.get("bundle_path") else None
    profile = describe_model_asset_bundle(load_model_asset_bundle(bundle_path))
    profile_path = write_json_artifact(run_dir, "model_assets_profile.json", profile)
    add_manifest_artifact(manifest, name="model_assets_profile", path=profile_path, kind="json")
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text="Loaded model asset profile.",
        payload_name="model_assets_profile_summary.json",
        payload=profile,
    )
    return finalize_and_respond(
        manifest=manifest,
        run_dir=run_dir,
        run_id=run_id,
        operation="model-asset-profile",
        summary="Loaded model asset profile.",
    )


def run_train_model_bundle_from_paths(
    *,
    dataset_path: str | None = None,
    file_path: str | None = None,
    output_root: str | None = None,
    options: Mapping[str, Any] | None = None,
) -> ToolExecutionResult:
    inputs = resolve_inputs(dataset_path=dataset_path, file_path=file_path)
    source_path = inputs.get("dataset_path") or inputs.get("file_path")
    run_id, run_dir = create_run("train-model-bundle", output_root)
    manifest = create_manifest(operation="train-model-bundle", run_id=run_id, run_dir=run_dir, inputs=inputs, options=options)
    bundle_path = str(options.get("bundle_path")) if options and options.get("bundle_path") else None
    bundle = train_forecast_model_bundle(
        source_path,
        output_path=bundle_path,
        max_rows=int(options.get("max_rows", 12000)) if options else 12000,
        sequence_length=int(options.get("sequence_length", 8)) if options else 8,
        lstm_epochs=int(options.get("lstm_epochs", 6)) if options else 6,
    )
    bundle_summary = {
        "bundle_metadata": bundle["metadata"],
        "bundle_description": describe_model_asset_bundle(bundle),
        "linear_rmse": bundle["learned_models"]["linear"]["rmse"],
        "rf_rmse": bundle["learned_models"]["rf"]["rmse"],
        "lstm_rmse": bundle["learned_models"]["lstm"]["rmse"],
    }
    profile_path = write_json_artifact(run_dir, "training_bundle_summary.json", bundle_summary)
    add_manifest_artifact(manifest, name="training_bundle_summary", path=profile_path, kind="json")
    write_summary_artifacts(
        run_dir=run_dir,
        manifest=manifest,
        summary_text="Trained and saved forecast model bundle.",
        payload_name="training_bundle_details.json",
        payload=bundle_summary,
    )
    return finalize_and_respond(
        manifest=manifest,
        run_dir=run_dir,
        run_id=run_id,
        operation="train-model-bundle",
        summary="Trained and saved forecast model bundle.",
    )


def setup_asset_tools(mcp_server: FastMCP) -> None:
    @mcp_server.tool(name="dataset_profile_from_paths")
    def dataset_profile_from_paths_tool(
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
        return run_dataset_profile_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )

    @mcp_server.tool(name="model_asset_profile")
    def model_asset_profile_tool(
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
        return run_model_asset_profile(output_root=output_root, options=options)

    @mcp_server.tool(name="train_model_bundle_from_paths")
    def train_model_bundle_from_paths_tool(
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
        return run_train_model_bundle_from_paths(
            dataset_path=dataset_path,
            file_path=file_path,
            output_root=output_root,
            options=options,
        )
