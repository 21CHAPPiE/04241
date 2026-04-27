from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .huadong_workflow import (
    DEFAULT_HUADONG_MCP_COMMAND,
    HUADONG_SCENARIO_IDS,
    HuadongWorkflowRequest,
    create_huadong_workflow_runner,
)


DEFAULT_CAPTURE_OUTPUT = "results/huadong_workflow_pydantic_io_capture.json"
DEFAULT_CAPTURE_RUN_ROOT = "results/agno-workflow-capture-runs"


def _json_options(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _step(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload["steps"][name]
    if not isinstance(value, dict):
        raise TypeError(f"Workflow step {name} is not a JSON object")
    return value


def _base_prepared_variables(workflow_output: dict[str, Any]) -> dict[str, Any]:
    prepared = _step(workflow_output, "prepare_inputs")
    variables = {
        "scenario_id": prepared["scenario_id"],
        "scenario_config": prepared["config"],
        "scenario_dir": prepared["scenario_dir"],
        "tool_run_root": prepared["tool_run_root"],
        "request": prepared["request"],
        "start_time": prepared.get("start_time"),
        "end_time": prepared.get("end_time"),
        "initial_end_time": prepared.get("initial_end_time"),
        "updated_end_time": prepared.get("updated_end_time"),
        "input_slice": prepared.get("input_slice"),
        "auxiliary_multistation_slice": prepared.get("auxiliary_multistation_slice"),
        "initial_input_slice": prepared.get("initial_input_slice"),
        "updated_input_slice": prepared.get("updated_input_slice"),
    }
    return {key: value for key, value in variables.items() if value is not None}


def _tool_call(
    *,
    workflow_output: dict[str, Any],
    step: str,
    tool_name: str,
    arguments_json: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step": step,
        "tool_name": tool_name,
        "arguments_json": arguments_json,
        "response_json": _step(workflow_output, step),
    }


def _build_tool_calls(workflow_output: dict[str, Any]) -> list[dict[str, Any]]:
    prepared = _step(workflow_output, "prepare_inputs")
    scenario_id = prepared["scenario_id"]
    tool_run_root = prepared["tool_run_root"]
    primary_dataset = prepared.get("initial_input_slice") or prepared.get("input_slice")
    calls: list[dict[str, Any]] = [
        _tool_call(
            workflow_output=workflow_output,
            step="primary_dataset_profile",
            tool_name="dataset_profile_from_paths",
            arguments_json={
                "dataset_path": primary_dataset,
                "output_root": tool_run_root,
                "options_json": _json_options({"profile_type": "basin"}),
            },
        )
    ]

    if scenario_id == "6.3.3":
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="auxiliary_dataset_profile",
                tool_name="dataset_profile_from_paths",
                arguments_json={
                    "dataset_path": prepared["auxiliary_multistation_slice"],
                    "output_root": tool_run_root,
                    "options_json": _json_options({"profile_type": "multistation"}),
                },
            )
        )

    calls.append(
        _tool_call(
            workflow_output=workflow_output,
            step="model_asset_profile",
            tool_name="model_asset_profile",
            arguments_json={"output_root": tool_run_root},
        )
    )

    if scenario_id == "6.3.2":
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="data_analysis",
                tool_name="data_analysis_from_paths",
                arguments_json={
                    "dataset_path": prepared["input_slice"],
                    "output_root": tool_run_root,
                    "options_json": _json_options({"column": "streamflow"}),
                },
            )
        )

    initial_forecast_output_root = (
        str(Path(tool_run_root) / "initial") if scenario_id == "6.3.4" else tool_run_root
    )
    calls.append(
        _tool_call(
            workflow_output=workflow_output,
            step="initial_forecast",
            tool_name="forecast_from_paths",
            arguments_json={
                "dataset_path": primary_dataset,
                "output_root": initial_forecast_output_root,
            },
        )
    )

    if scenario_id in {"6.3.3", "6.3.4"}:
        initial_forecast = _step(workflow_output, "initial_forecast")
        observation_dataset = prepared.get("initial_input_slice") or prepared.get("input_slice")
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="initial_ensemble",
                tool_name="ensemble_from_paths",
                arguments_json={
                    "file_path": initial_forecast["artifact_paths"]["forecast"],
                    "output_root": initial_forecast_output_root,
                    "options_json": _json_options(
                        {
                            "method": "bma",
                            "observation_dataset": observation_dataset,
                            "observation_column": "streamflow",
                        }
                    ),
                },
            )
        )
        initial_ensemble = _step(workflow_output, "initial_ensemble")
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="initial_correction",
                tool_name="correction_from_paths",
                arguments_json={
                    "file_path": initial_ensemble["artifact_paths"]["ensemble"],
                    "output_root": initial_forecast_output_root,
                    "options_json": _json_options(
                        {
                            "observation_dataset": observation_dataset,
                            "observation_column": "streamflow",
                        }
                    ),
                },
            )
        )

    if scenario_id == "6.3.4":
        updated_output_root = str(Path(tool_run_root) / "updated")
        calls.extend(
            [
                _tool_call(
                    workflow_output=workflow_output,
                    step="updated_dataset_profile",
                    tool_name="dataset_profile_from_paths",
                    arguments_json={
                        "dataset_path": prepared["updated_input_slice"],
                        "output_root": tool_run_root,
                        "options_json": _json_options({"profile_type": "basin"}),
                    },
                ),
                _tool_call(
                    workflow_output=workflow_output,
                    step="updated_forecast",
                    tool_name="forecast_from_paths",
                    arguments_json={
                        "dataset_path": prepared["updated_input_slice"],
                        "output_root": updated_output_root,
                    },
                ),
            ]
        )
        updated_forecast = _step(workflow_output, "updated_forecast")
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="updated_ensemble",
                tool_name="ensemble_from_paths",
                arguments_json={
                    "file_path": updated_forecast["artifact_paths"]["forecast"],
                    "output_root": updated_output_root,
                    "options_json": _json_options(
                        {
                            "method": "bma",
                            "observation_dataset": prepared["updated_input_slice"],
                            "observation_column": "streamflow",
                        }
                    ),
                },
            )
        )
        updated_ensemble = _step(workflow_output, "updated_ensemble")
        calls.append(
            _tool_call(
                workflow_output=workflow_output,
                step="updated_correction",
                tool_name="correction_from_paths",
                arguments_json={
                    "file_path": updated_ensemble["artifact_paths"]["ensemble"],
                    "output_root": updated_output_root,
                    "options_json": _json_options(
                        {
                            "observation_dataset": prepared["updated_input_slice"],
                            "observation_column": "streamflow",
                        }
                    ),
                },
            )
        )

    return calls


def _build_skipped_steps(workflow_output: dict[str, Any]) -> list[dict[str, Any]]:
    skipped = []
    for step_name, value in workflow_output["steps"].items():
        if isinstance(value, dict) and value.get("skipped"):
            skipped.append({"step": step_name, "reason": value.get("reason")})
    return skipped


def _build_capture_run(
    *,
    request: HuadongWorkflowRequest,
    workflow_output: dict[str, Any],
) -> dict[str, Any]:
    prepared = _step(workflow_output, "prepare_inputs")
    return {
        "workflow_request_json": request.model_dump(mode="json"),
        "resolved_workflow_request_json": prepared["request"],
        "intermediate_variables_json": _base_prepared_variables(workflow_output),
        "tool_calls": _build_tool_calls(workflow_output),
        "skipped_steps": _build_skipped_steps(workflow_output),
        "step_outputs_json": workflow_output["steps"],
        "report_json": workflow_output["report"],
        "workflow_output_json": workflow_output,
    }


async def build_capture(
    *,
    scenario_ids: list[str],
    output_root: str,
    mcp_command: str,
) -> dict[str, Any]:
    runner = create_huadong_workflow_runner(mcp_command=mcp_command)
    capture: dict[str, Any] = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "description": (
            "Real JSON inputs, intermediate variables, MCP tool arguments, "
            "tool responses, and workflow outputs captured by executing the "
            "Huadong Agno workflow with a Python script."
        ),
        "capture_method": "python_script_runtime_execution",
        "llm_generated": False,
        "server_command_used_by_capture": mcp_command,
        "pydantic_models": {
            "HuadongWorkflowRequest": {
                "json_schema": HuadongWorkflowRequest.model_json_schema()
            }
        },
        "workflow_runs": {},
    }

    for scenario_id in scenario_ids:
        request = HuadongWorkflowRequest(scenario_id=scenario_id, output_root=output_root)
        result = await runner.run(request)
        workflow_output = result.content if hasattr(result, "content") else result
        if not isinstance(workflow_output, dict):
            raise TypeError(f"Workflow output for {scenario_id} is not a JSON object")
        capture["workflow_runs"][scenario_id] = _build_capture_run(
            request=request,
            workflow_output=workflow_output,
        )

    return capture


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture full Huadong Agno workflow I/O by executing the workflow."
    )
    parser.add_argument(
        "--scenario-id",
        action="append",
        choices=[*HUADONG_SCENARIO_IDS, "all"],
        default=None,
        help="Scenario id to capture. Repeat for multiple scenarios, or use all.",
    )
    parser.add_argument("--output-root", default=DEFAULT_CAPTURE_RUN_ROOT)
    parser.add_argument("--output", default=DEFAULT_CAPTURE_OUTPUT)
    parser.add_argument("--mcp-command", default=DEFAULT_HUADONG_MCP_COMMAND)
    return parser


async def _run_async(args: argparse.Namespace) -> int:
    selected = args.scenario_id or ["all"]
    scenario_ids = list(HUADONG_SCENARIO_IDS) if "all" in selected else selected
    capture = await build_capture(
        scenario_ids=scenario_ids,
        output_root=args.output_root,
        mcp_command=args.mcp_command,
    )
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(capture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(output_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run_async(build_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
