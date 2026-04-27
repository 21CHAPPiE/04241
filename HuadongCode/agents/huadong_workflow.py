from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

from agno.tools.function import FunctionCall
from agno.tools.mcp import MCPTools
from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from pydantic import BaseModel

from experiments.benchmark.common import (
    build_benchmark_run_root,
    load_artifact_json,
    slice_basin_dataset,
    slice_multistation_dataset,
    summarize_model_spread,
    summarize_peak_and_window,
    summarize_tail_window,
    write_scenario_report,
)


_PYTHON_DIR = str(Path(sys.executable).resolve().parent)
if os.environ.get("PATH", "").split(os.pathsep)[0] != _PYTHON_DIR:
    os.environ["PATH"] = _PYTHON_DIR + os.pathsep + os.environ.get("PATH", "")

DEFAULT_HUADONG_MCP_COMMAND = "python -m app.server"
DEFAULT_WORKFLOW_OUTPUT_ROOT = "results/agno-workflow-runs"
HUADONG_SCENARIO_IDS = ("6.3.1", "6.3.2", "6.3.3", "6.3.4")
MODEL_COLUMNS = ["forecast_xinanjiang", "forecast_gr4j", "forecast_rf", "forecast_lstm"]


SCENARIO_CONFIGS: dict[str, dict[str, Any]] = {
    "6.3.1": {
        "slug": "6.3.1-quick-forecast",
        "title": "Quick Forecast Service Demo",
        "goal": "Run the shortest deterministic forecast workflow through MCP tools.",
        "start_time": "2015-08-08 18:00",
        "end_time": "2015-08-09 06:00",
        "task_type": "quick_forecast",
    },
    "6.3.2": {
        "slug": "6.3.2-standard-forecast",
        "title": "Standard Forecast Workflow Demo",
        "goal": "Run dataset profiling, model loading, data analysis, and forecasting through MCP tools.",
        "start_time": "2016-09-27 18:00",
        "end_time": "2016-09-28 18:00",
        "task_type": "standard_forecast",
    },
    "6.3.3": {
        "slug": "6.3.3-complex-flood",
        "title": "Complex Flood Multi-Tool Forecast Demo",
        "goal": "Run a complex flood replay with forecast, ensemble, and correction through MCP tools.",
        "start_time": "2016-09-28 00:00",
        "end_time": "2016-09-29 00:00",
        "task_type": "complex_flood_forecast",
    },
    "6.3.4": {
        "slug": "6.3.4-rolling-update",
        "title": "Rolling Update and Reforecast Demo",
        "goal": "Run an initial forecast and a deterministic update rerun through MCP tools.",
        "start_time": "2016-09-28 00:00",
        "initial_end_time": "2016-09-28 12:00",
        "updated_end_time": "2016-09-28 18:00",
        "task_type": "rolling_forecast_update",
    },
}


class HuadongWorkflowRequest(BaseModel):
    scenario_id: str
    output_root: str | None = DEFAULT_WORKFLOW_OUTPUT_ROOT
    start_time: str | None = None
    end_time: str | None = None
    initial_end_time: str | None = None
    updated_end_time: str | None = None
    basin_dataset_path: str = "data/basin_001_hourly.csv"
    multistation_dataset_path: str = "data/rain_15stations_flow.csv"


class HuadongWorkflowRunner:
    """Run fixed Agno workflow steps against the local Huadong MCP server."""

    def __init__(self, *, mcp_command: str = DEFAULT_HUADONG_MCP_COMMAND) -> None:
        self.mcp_command = mcp_command
        self._mcp_tools: MCPTools | None = None
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> Workflow:
        return Workflow(
            name="Huadong MCP Fixed Workflow",
            description=(
                "Deterministic Agno workflow for Huadong benchmark scenarios. "
                "It calls MCP tools directly and does not instantiate an Agent."
            ),
            steps=[
                Step(name="prepare_inputs", executor=self._prepare_inputs_step),
                Step(name="primary_dataset_profile", executor=self._primary_dataset_profile_step),
                Step(name="auxiliary_dataset_profile", executor=self._auxiliary_dataset_profile_step),
                Step(name="model_asset_profile", executor=self._model_asset_profile_step),
                Step(name="data_analysis", executor=self._data_analysis_step),
                Step(name="initial_forecast", executor=self._initial_forecast_step),
                Step(name="initial_ensemble", executor=self._initial_ensemble_step),
                Step(name="initial_correction", executor=self._initial_correction_step),
                Step(name="updated_dataset_profile", executor=self._updated_dataset_profile_step),
                Step(name="updated_forecast", executor=self._updated_forecast_step),
                Step(name="updated_ensemble", executor=self._updated_ensemble_step),
                Step(name="updated_correction", executor=self._updated_correction_step),
                Step(name="assemble_result", executor=self._assemble_result_step),
            ],
        )

    async def run(self, request: HuadongWorkflowRequest | dict[str, Any]) -> Any:
        normalized = (
            request
            if isinstance(request, HuadongWorkflowRequest)
            else HuadongWorkflowRequest.model_validate(request)
        )
        self._validate_request(normalized)
        async with MCPTools(command=self.mcp_command) as mcp_tools:
            self._mcp_tools = mcp_tools
            try:
                return await self.workflow.arun(input=normalized.model_dump(mode="json"))
            finally:
                self._mcp_tools = None

    def run_sync(self, request: HuadongWorkflowRequest | dict[str, Any]) -> Any:
        return asyncio.run(self.run(request))

    async def run_many(self, requests: list[HuadongWorkflowRequest | dict[str, Any]]) -> dict[str, Any]:
        normalized_requests = [
            request if isinstance(request, HuadongWorkflowRequest) else HuadongWorkflowRequest.model_validate(request)
            for request in requests
        ]
        for request in normalized_requests:
            self._validate_request(request)
        async with MCPTools(command=self.mcp_command) as mcp_tools:
            self._mcp_tools = mcp_tools
            try:
                results: dict[str, Any] = {}
                for request in normalized_requests:
                    output = await self.workflow.arun(input=request.model_dump(mode="json"))
                    results[request.scenario_id] = output.content if hasattr(output, "content") else output
                return {
                    "workflow": {
                        "name": self.workflow.name,
                        "mode": "deterministic_mcp_steps_batch",
                        "mcp_command": self.mcp_command,
                    },
                    "scenario_ids": [request.scenario_id for request in normalized_requests],
                    "results": results,
                }
            finally:
                self._mcp_tools = None

    async def run_all(self, *, output_root: str | None = DEFAULT_WORKFLOW_OUTPUT_ROOT) -> dict[str, Any]:
        return await self.run_many(
            [HuadongWorkflowRequest(scenario_id=scenario_id, output_root=output_root) for scenario_id in HUADONG_SCENARIO_IDS]
        )

    @staticmethod
    def _validate_request(request: HuadongWorkflowRequest) -> None:
        if request.scenario_id not in SCENARIO_CONFIGS:
            supported = ", ".join(HUADONG_SCENARIO_IDS)
            raise ValueError(f"Unsupported scenario_id {request.scenario_id!r}; supported: {supported}")

    async def _call_mcp_tool(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        if self._mcp_tools is None:
            raise RuntimeError("MCP tools are not connected")
        try:
            function = self._mcp_tools.functions[tool_name]
        except KeyError as exc:
            raise RuntimeError(f"MCP tool is not available: {tool_name}") from exc

        clean_arguments = {key: value for key, value in arguments.items() if value is not None}
        execution = await FunctionCall(function=function, arguments=clean_arguments).aexecute()
        if execution.status != "success":
            raise RuntimeError(execution.error or f"MCP tool call failed: {tool_name}")
        return self._parse_json_payload(getattr(execution.result, "content", execution.result), tool_name=tool_name)

    @staticmethod
    def _parse_json_payload(content: Any, *, tool_name: str) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise RuntimeError(f"Unsupported MCP result type from {tool_name}: {type(content).__name__}")
        normalized = content.strip()
        if not normalized:
            return {}
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            start = normalized.find("{")
            end = normalized.rfind("}")
            if start == -1 or end == -1 or end < start:
                raise RuntimeError(f"Failed to parse JSON result from {tool_name}: {normalized}") from None
            parsed = json.loads(normalized[start : end + 1])
        if not isinstance(parsed, dict):
            raise RuntimeError(f"MCP tool {tool_name} returned non-object JSON")
        return parsed

    @staticmethod
    def _request_from_input(step_input: StepInput) -> HuadongWorkflowRequest:
        if step_input.input is None:
            raise ValueError("Workflow input is required")
        return HuadongWorkflowRequest.model_validate(step_input.input)

    @staticmethod
    def _prepared(step_input: StepInput) -> dict[str, Any]:
        prepared = step_input.get_step_content("prepare_inputs")
        if not isinstance(prepared, dict):
            raise RuntimeError("Missing prepare_inputs output")
        return prepared

    @staticmethod
    def _step_content(step_input: StepInput, step_name: str) -> dict[str, Any]:
        content = step_input.get_step_content(step_name)
        if isinstance(content, dict):
            return content
        return {"skipped": True, "reason": f"{step_name}_not_available"}

    @staticmethod
    def _skipped(reason: str) -> StepOutput:
        return StepOutput(content={"skipped": True, "reason": reason})

    async def _prepare_inputs_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        config = SCENARIO_CONFIGS[request.scenario_id]
        scenario_dir = build_benchmark_run_root(config["slug"], request.output_root)
        payload: dict[str, Any] = {
            "scenario_id": request.scenario_id,
            "config": config,
            "scenario_dir": str(scenario_dir),
            "tool_run_root": str(scenario_dir / "tool_runs"),
            "request": request.model_dump(mode="json"),
        }

        if request.scenario_id == "6.3.4":
            start_time = request.start_time or config["start_time"]
            initial_end_time = request.initial_end_time or config["initial_end_time"]
            updated_end_time = request.updated_end_time or config["updated_end_time"]
            initial_slice = slice_basin_dataset(
                request.basin_dataset_path,
                start_time,
                initial_end_time,
                scenario_dir / "initial_input_slice.csv",
            )
            updated_slice = slice_basin_dataset(
                request.basin_dataset_path,
                start_time,
                updated_end_time,
                scenario_dir / "updated_input_slice.csv",
            )
            payload.update(
                {
                    "start_time": start_time,
                    "initial_end_time": initial_end_time,
                    "updated_end_time": updated_end_time,
                    "initial_input_slice": str(initial_slice),
                    "updated_input_slice": str(updated_slice),
                }
            )
        else:
            start_time = request.start_time or config["start_time"]
            end_time = request.end_time or config["end_time"]
            basin_slice = slice_basin_dataset(
                request.basin_dataset_path,
                start_time,
                end_time,
                scenario_dir / "input_slice.csv",
            )
            payload.update(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "input_slice": str(basin_slice),
                }
            )
            if request.scenario_id == "6.3.3":
                multistation_slice = slice_multistation_dataset(
                    request.multistation_dataset_path,
                    start_time,
                    end_time,
                    scenario_dir / "auxiliary_multistation_slice.csv",
                )
                payload["auxiliary_multistation_slice"] = str(multistation_slice)
        return StepOutput(content=payload)

    async def _primary_dataset_profile_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        dataset_path = prepared.get("initial_input_slice") or prepared.get("input_slice")
        payload = await self._call_mcp_tool(
            "dataset_profile_from_paths",
            dataset_path=dataset_path,
            output_root=prepared["tool_run_root"],
            options_json=json.dumps({"profile_type": "basin"}),
        )
        return StepOutput(content=payload)

    async def _auxiliary_dataset_profile_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.3":
            return self._skipped("scenario_has_no_auxiliary_multistation_profile")
        payload = await self._call_mcp_tool(
            "dataset_profile_from_paths",
            dataset_path=prepared["auxiliary_multistation_slice"],
            output_root=prepared["tool_run_root"],
            options_json=json.dumps({"profile_type": "multistation"}),
        )
        return StepOutput(content=payload)

    async def _model_asset_profile_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        payload = await self._call_mcp_tool("model_asset_profile", output_root=prepared["tool_run_root"])
        return StepOutput(content=payload)

    async def _data_analysis_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.2":
            return self._skipped("scenario_has_no_data_analysis_step")
        payload = await self._call_mcp_tool(
            "data_analysis_from_paths",
            dataset_path=prepared["input_slice"],
            output_root=prepared["tool_run_root"],
            options_json=json.dumps({"column": "streamflow"}),
        )
        return StepOutput(content=payload)

    async def _initial_forecast_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        dataset_path = prepared.get("initial_input_slice") or prepared.get("input_slice")
        output_root = str(Path(prepared["tool_run_root"]) / "initial") if prepared["scenario_id"] == "6.3.4" else prepared["tool_run_root"]
        payload = await self._call_mcp_tool(
            "forecast_from_paths",
            dataset_path=dataset_path,
            output_root=output_root,
        )
        return StepOutput(content=payload)

    async def _initial_ensemble_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] not in {"6.3.3", "6.3.4"}:
            return self._skipped("scenario_has_no_initial_ensemble_step")
        forecast = self._step_content(step_input, "initial_forecast")
        dataset_path = prepared.get("initial_input_slice") or prepared.get("input_slice")
        output_root = str(Path(prepared["tool_run_root"]) / "initial") if prepared["scenario_id"] == "6.3.4" else prepared["tool_run_root"]
        payload = await self._call_mcp_tool(
            "ensemble_from_paths",
            file_path=forecast["artifact_paths"]["forecast"],
            output_root=output_root,
            options_json=json.dumps(
                {
                    "method": "bma",
                    "observation_dataset": dataset_path,
                    "observation_column": "streamflow",
                },
                ensure_ascii=False,
            ),
        )
        return StepOutput(content=payload)

    async def _initial_correction_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] not in {"6.3.3", "6.3.4"}:
            return self._skipped("scenario_has_no_initial_correction_step")
        ensemble = self._step_content(step_input, "initial_ensemble")
        dataset_path = prepared.get("initial_input_slice") or prepared.get("input_slice")
        output_root = str(Path(prepared["tool_run_root"]) / "initial") if prepared["scenario_id"] == "6.3.4" else prepared["tool_run_root"]
        payload = await self._call_mcp_tool(
            "correction_from_paths",
            file_path=ensemble["artifact_paths"]["ensemble"],
            output_root=output_root,
            options_json=json.dumps(
                {"observation_dataset": dataset_path, "observation_column": "streamflow"},
                ensure_ascii=False,
            ),
        )
        return StepOutput(content=payload)

    async def _updated_dataset_profile_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.4":
            return self._skipped("scenario_has_no_updated_dataset_profile")
        payload = await self._call_mcp_tool(
            "dataset_profile_from_paths",
            dataset_path=prepared["updated_input_slice"],
            output_root=prepared["tool_run_root"],
            options_json=json.dumps({"profile_type": "basin"}),
        )
        return StepOutput(content=payload)

    async def _updated_forecast_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.4":
            return self._skipped("scenario_has_no_updated_forecast_step")
        payload = await self._call_mcp_tool(
            "forecast_from_paths",
            dataset_path=prepared["updated_input_slice"],
            output_root=str(Path(prepared["tool_run_root"]) / "updated"),
        )
        return StepOutput(content=payload)

    async def _updated_ensemble_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.4":
            return self._skipped("scenario_has_no_updated_ensemble_step")
        forecast = self._step_content(step_input, "updated_forecast")
        payload = await self._call_mcp_tool(
            "ensemble_from_paths",
            file_path=forecast["artifact_paths"]["forecast"],
            output_root=str(Path(prepared["tool_run_root"]) / "updated"),
            options_json=json.dumps(
                {
                    "method": "bma",
                    "observation_dataset": prepared["updated_input_slice"],
                    "observation_column": "streamflow",
                },
                ensure_ascii=False,
            ),
        )
        return StepOutput(content=payload)

    async def _updated_correction_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        if prepared["scenario_id"] != "6.3.4":
            return self._skipped("scenario_has_no_updated_correction_step")
        ensemble = self._step_content(step_input, "updated_ensemble")
        payload = await self._call_mcp_tool(
            "correction_from_paths",
            file_path=ensemble["artifact_paths"]["ensemble"],
            output_root=str(Path(prepared["tool_run_root"]) / "updated"),
            options_json=json.dumps(
                {"observation_dataset": prepared["updated_input_slice"], "observation_column": "streamflow"},
                ensure_ascii=False,
            ),
        )
        return StepOutput(content=payload)

    async def _assemble_result_step(self, step_input: StepInput) -> StepOutput:
        prepared = self._prepared(step_input)
        scenario_id = prepared["scenario_id"]
        report = self._build_report(step_input, prepared)
        scenario_dir = Path(prepared["scenario_dir"])
        report_json = write_scenario_report(scenario_dir / "workflow_report.json", report)
        report_md = write_scenario_report(scenario_dir / "workflow_report.md", report)
        report["artifacts"]["workflow_report_json"] = str(report_json)
        report["artifacts"]["workflow_report_md"] = str(report_md)
        write_scenario_report(report_json, report)
        write_scenario_report(report_md, report)
        return StepOutput(
            content={
                "workflow": {
                    "name": self.workflow.name,
                    "mode": "deterministic_mcp_steps",
                    "mcp_command": self.mcp_command,
                },
                "request": prepared["request"],
                "scenario_id": scenario_id,
                "scenario_dir": prepared["scenario_dir"],
                "report": report,
                "steps": {
                    name: self._step_content(step_input, name)
                    for name in (
                        "prepare_inputs",
                        "primary_dataset_profile",
                        "auxiliary_dataset_profile",
                        "model_asset_profile",
                        "data_analysis",
                        "initial_forecast",
                        "initial_ensemble",
                        "initial_correction",
                        "updated_dataset_profile",
                        "updated_forecast",
                        "updated_ensemble",
                        "updated_correction",
                    )
                },
            }
        )

    def _build_report(self, step_input: StepInput, prepared: dict[str, Any]) -> dict[str, Any]:
        scenario_id = prepared["scenario_id"]
        config = prepared["config"]
        primary_profile = self._step_content(step_input, "primary_dataset_profile")
        auxiliary_profile = self._step_content(step_input, "auxiliary_dataset_profile")
        model_profile = self._step_content(step_input, "model_asset_profile")
        data_analysis = self._step_content(step_input, "data_analysis")
        initial_forecast = self._step_content(step_input, "initial_forecast")
        initial_ensemble = self._step_content(step_input, "initial_ensemble")
        initial_correction = self._step_content(step_input, "initial_correction")
        updated_profile = self._step_content(step_input, "updated_dataset_profile")
        updated_forecast = self._step_content(step_input, "updated_forecast")
        updated_correction = self._step_content(step_input, "updated_correction")

        workflow_steps = self._report_steps(prepared, step_input)
        report: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_title": config["title"],
            "scene_goal": config["goal"],
            "user_input_examples": self._user_input_examples(scenario_id),
            "task_recognition": self._task_recognition(prepared),
            "workflow_engine": {
                "library": "agno.workflow",
                "agent_used": False,
                "mcp_command": self.mcp_command,
            },
            "workflow_steps": workflow_steps,
            "tool_calls": [
                self._tool_call_summary(name, self._step_content(step_input, name))
                for name in (
                    "primary_dataset_profile",
                    "auxiliary_dataset_profile",
                    "model_asset_profile",
                    "data_analysis",
                    "initial_forecast",
                    "initial_ensemble",
                    "initial_correction",
                    "updated_dataset_profile",
                    "updated_forecast",
                    "updated_ensemble",
                    "updated_correction",
                )
                if not self._step_content(step_input, name).get("skipped")
            ],
            "artifacts": self._artifacts(prepared, step_input),
            "result_summary": {},
            "verification_points": [
                "Agno Workflow executes fixed steps without Agent or model inference.",
                "Every computational node after input slicing is called through the MCP server.",
                "Inputs and outputs are represented as paths and JSON artifacts for interface testing.",
            ],
        }

        forecast_csv = Path(initial_forecast["artifact_paths"]["forecast"])
        report["result_summary"].update(
            {
                "primary_dataset_profile": load_artifact_json(primary_profile["artifact_paths"]["dataset_profile"]),
                "model_asset_profile": load_artifact_json(model_profile["artifact_paths"]["model_assets_profile"]),
                "forecast_peaks": {column: summarize_peak_and_window(forecast_csv, column) for column in MODEL_COLUMNS},
                "observed_window": summarize_peak_and_window(forecast_csv, "observed"),
                "tool_summaries": {"forecast": initial_forecast["small_summary"]},
            }
        )

        if scenario_id == "6.3.2":
            analysis_json = load_artifact_json(data_analysis["artifact_paths"]["analysis"])
            report["result_summary"].update(
                {
                    "trend_analysis": analysis_json["trend"],
                    "cycle_analysis": analysis_json["cycle"],
                    "mutation_analysis": analysis_json["mutation"],
                    "tool_summaries": {
                        "analysis": data_analysis["small_summary"],
                        "forecast": initial_forecast["small_summary"],
                    },
                }
            )
        elif scenario_id == "6.3.3":
            ensemble_csv = Path(initial_ensemble["artifact_paths"]["ensemble"])
            corrected_csv = Path(initial_correction["artifact_paths"]["correction"])
            ensemble_details = load_artifact_json(initial_ensemble["artifact_paths"]["ensemble_details"])
            correction_details = load_artifact_json(initial_correction["artifact_paths"]["correction_details"])
            report["result_summary"].update(
                {
                    "auxiliary_dataset_profile": load_artifact_json(auxiliary_profile["artifact_paths"]["dataset_profile"]),
                    "ensemble_peak": summarize_peak_and_window(ensemble_csv, "ensemble_forecast"),
                    "corrected_peak": summarize_peak_and_window(corrected_csv, "corrected_forecast"),
                    "screening": ensemble_details["screening"],
                    "selected_model_names": ensemble_details["selected_model_names"],
                    "error_metrics": correction_details["error_metrics"],
                    "model_difference_summary": summarize_model_spread(forecast_csv, MODEL_COLUMNS),
                    "tool_summaries": {
                        "forecast": initial_forecast["small_summary"],
                        "ensemble": initial_ensemble["small_summary"],
                        "correction": initial_correction["small_summary"],
                    },
                }
            )
        elif scenario_id == "6.3.4":
            initial_corrected_csv = Path(initial_correction["artifact_paths"]["correction"])
            updated_corrected_csv = Path(updated_correction["artifact_paths"]["correction"])
            initial_peak = summarize_peak_and_window(initial_corrected_csv, "corrected_forecast")
            updated_peak = summarize_peak_and_window(updated_corrected_csv, "corrected_forecast")
            report["result_summary"].update(
                {
                    "updated_dataset_profile": load_artifact_json(updated_profile["artifact_paths"]["dataset_profile"]),
                    "update_trigger_reason": "New observations extend the forecast context and trigger a deterministic rerun.",
                    "rerun_steps": ["forecast_from_paths", "ensemble_from_paths", "correction_from_paths"],
                    "initial_vs_updated_peak": {"initial": initial_peak, "updated": updated_peak},
                    "initial_vs_updated_tail_window": {
                        "initial": summarize_tail_window(initial_corrected_csv, "corrected_forecast"),
                        "updated": summarize_tail_window(updated_corrected_csv, "corrected_forecast"),
                    },
                    "delta_summary": {
                        "peak_value_delta": round((updated_peak["peak_value"] or 0.0) - (initial_peak["peak_value"] or 0.0), 3),
                        "initial_length": initial_peak["n_values"],
                        "updated_length": updated_peak["n_values"],
                    },
                    "tool_summaries": {
                        "initial_forecast": initial_forecast["small_summary"],
                        "updated_forecast": updated_forecast["small_summary"],
                    },
                }
            )

        return report

    @staticmethod
    def _user_input_examples(scenario_id: str) -> list[str]:
        examples = {
            "6.3.1": ["Please run a quick inflow forecast.", "Run the shortest forecast workflow."],
            "6.3.2": ["Please generate a standard 24-hour inflow forecast.", "Include data analysis before forecasting."],
            "6.3.3": ["Replay a complex flood and consolidate the forecast.", "Run forecast, ensemble, and correction."],
            "6.3.4": ["Update the previous forecast when new observations arrive.", "Run initial and updated forecasts for comparison."],
        }
        return examples[scenario_id]

    @staticmethod
    def _task_recognition(prepared: dict[str, Any]) -> dict[str, Any]:
        config = prepared["config"]
        time_range = {
            "start": prepared["start_time"],
            "end": prepared.get("end_time"),
            "initial_end": prepared.get("initial_end_time"),
            "updated_end": prepared.get("updated_end_time"),
        }
        return {
            "task_type": config["task_type"],
            "target_object": "basin inflow",
            "time_range": {key: value for key, value in time_range.items() if value is not None},
            "output_requirements": ["artifact paths", "JSON report", "business summary"],
        }

    @staticmethod
    def _tool_call_summary(step_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "step_name": step_name,
            "operation": payload.get("operation"),
            "run_id": payload.get("run_id"),
            "status": payload.get("status"),
            "output_manifest_path": payload.get("output_manifest_path"),
        }

    def _report_steps(self, prepared: dict[str, Any], step_input: StepInput) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "step_name": "prepare_inputs",
                "tool_name": "local_dataset_slice",
                "input": prepared["request"],
                "output": prepared.get("input_slice") or prepared.get("initial_input_slice"),
                "status": "completed",
            }
        ]
        for step_name, tool_name in (
            ("primary_dataset_profile", "dataset_profile_from_paths"),
            ("auxiliary_dataset_profile", "dataset_profile_from_paths"),
            ("model_asset_profile", "model_asset_profile"),
            ("data_analysis", "data_analysis_from_paths"),
            ("initial_forecast", "forecast_from_paths"),
            ("initial_ensemble", "ensemble_from_paths"),
            ("initial_correction", "correction_from_paths"),
            ("updated_dataset_profile", "dataset_profile_from_paths"),
            ("updated_forecast", "forecast_from_paths"),
            ("updated_ensemble", "ensemble_from_paths"),
            ("updated_correction", "correction_from_paths"),
        ):
            payload = self._step_content(step_input, step_name)
            if payload.get("skipped"):
                continue
            rows.append(
                {
                    "step_name": step_name,
                    "tool_name": tool_name,
                    "input": "path arguments from previous workflow steps",
                    "output": payload.get("artifact_paths") or payload.get("output_manifest_path"),
                    "status": payload.get("status", "completed"),
                }
            )
        return rows

    def _artifacts(self, prepared: dict[str, Any], step_input: StepInput) -> dict[str, Any]:
        artifacts: dict[str, Any] = {"scenario_dir": prepared["scenario_dir"], "tool_run_root": prepared["tool_run_root"]}
        for key in ("input_slice", "auxiliary_multistation_slice", "initial_input_slice", "updated_input_slice"):
            if key in prepared:
                artifacts[key] = prepared[key]
        for step_name in (
            "primary_dataset_profile",
            "auxiliary_dataset_profile",
            "model_asset_profile",
            "data_analysis",
            "initial_forecast",
            "initial_ensemble",
            "initial_correction",
            "updated_dataset_profile",
            "updated_forecast",
            "updated_ensemble",
            "updated_correction",
        ):
            payload = self._step_content(step_input, step_name)
            if not payload.get("skipped") and "artifact_paths" in payload:
                artifacts[step_name] = payload["artifact_paths"]
        return artifacts


def create_huadong_workflow_runner(*, mcp_command: str = DEFAULT_HUADONG_MCP_COMMAND) -> HuadongWorkflowRunner:
    return HuadongWorkflowRunner(mcp_command=mcp_command)
