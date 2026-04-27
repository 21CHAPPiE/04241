from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

from pydantic import BaseModel

from agno.tools.function import FunctionCall
from agno.tools.mcp import MCPTools
from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput
from project.tanken_config import TANKEN_CASES, get_tanken_case
from project.utils.event_io import resolve_event_path


_PYTHON_DIR = str(Path(sys.executable).resolve().parent)
if os.environ.get("PATH", "").split(os.pathsep)[0] != _PYTHON_DIR:
    os.environ["PATH"] = _PYTHON_DIR + os.pathsep + os.environ.get("PATH", "")

DEFAULT_TANKEN_MCP_COMMAND = "python -m project.tanken_mcp_server"
DEFAULT_TANKEN_CASE_IDS = tuple(TANKEN_CASES.keys())


class TankenWorkflowRequest(BaseModel):
    case_id: str
    event_csv_path: str | None = None
    reservoir_config_path: str | None = None
    persist_result: bool = False
    include_case_report: bool = True


class TankenWorkflowRunner:
    """Run a fixed Agno workflow that calls the local Tanken MCP server."""

    def __init__(self, *, mcp_command: str = DEFAULT_TANKEN_MCP_COMMAND) -> None:
        self.mcp_command = mcp_command
        self._mcp_tools: MCPTools | None = None
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> Workflow:
        return Workflow(
            name="Tanken MCP Fixed Workflow",
            description=(
                "A deterministic Agno workflow that executes prewritten Tanken dispatch "
                "steps through the local MCP server without model inference."
            ),
            steps=[
                Step(name="describe_case", executor=self._describe_case_step),
                Step(name="get_status", executor=self._get_status_step),
                Step(name="get_rules", executor=self._get_rules_step),
                Step(name="optimize_plan", executor=self._optimize_plan_step),
                Step(name="simulate_plan", executor=self._simulate_plan_step),
                Step(name="evaluate_plan", executor=self._evaluate_plan_step),
                Step(name="run_case_report", executor=self._run_case_report_step),
                Step(name="assemble_result", executor=self._assemble_result_step),
            ],
        )

    async def run(self, request: TankenWorkflowRequest | dict[str, Any]) -> Any:
        return await self.run_case(request)

    async def run_case(self, request: TankenWorkflowRequest | dict[str, Any]) -> Any:
        normalized = (
            request
            if isinstance(request, TankenWorkflowRequest)
            else TankenWorkflowRequest.model_validate(request)
        )
        normalized = self.normalize_request(normalized)
        async with MCPTools(command=self.mcp_command) as mcp_tools:
            self._mcp_tools = mcp_tools
            try:
                return await self.workflow.arun(input=normalized.model_dump(mode="json"))
            finally:
                self._mcp_tools = None

    def run_sync(self, request: TankenWorkflowRequest | dict[str, Any]) -> Any:
        return asyncio.run(self.run(request))

    async def run_many(self, requests: list[TankenWorkflowRequest | dict[str, Any]]) -> dict[str, Any]:
        normalized_requests = [self.normalize_request(item) for item in requests]
        async with MCPTools(command=self.mcp_command) as mcp_tools:
            self._mcp_tools = mcp_tools
            try:
                results: dict[str, Any] = {}
                for request in normalized_requests:
                    output = await self.workflow.arun(input=request.model_dump(mode="json"))
                    results[request.case_id] = output.content if hasattr(output, "content") else output
                return {
                    "workflow": {
                        "name": self.workflow.name,
                        "mode": "deterministic_mcp_steps_batch",
                        "mcp_command": self.mcp_command,
                    },
                    "case_ids": [request.case_id for request in normalized_requests],
                    "results": results,
                }
            finally:
                self._mcp_tools = None

    async def run_all_cases(
        self,
        *,
        persist_result: bool = False,
        include_case_report: bool = True,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        requests = [
            self.build_request(
                case_id=case_id,
                persist_result=persist_result,
                include_case_report=include_case_report,
                reservoir_config_path=reservoir_config_path,
            )
            for case_id in DEFAULT_TANKEN_CASE_IDS
        ]
        return await self.run_many(requests)

    def run_all_cases_sync(
        self,
        *,
        persist_result: bool = False,
        include_case_report: bool = True,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.run_all_cases(
                persist_result=persist_result,
                include_case_report=include_case_report,
                reservoir_config_path=reservoir_config_path,
            )
        )

    @staticmethod
    def build_request(
        *,
        case_id: str,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
        persist_result: bool = False,
        include_case_report: bool = True,
    ) -> TankenWorkflowRequest:
        case = get_tanken_case(case_id)
        resolved_event_csv_path = (
            event_csv_path
            if event_csv_path is not None
            else str(resolve_event_path(None, case))
        )
        return TankenWorkflowRequest(
            case_id=case_id,
            event_csv_path=resolved_event_csv_path,
            reservoir_config_path=reservoir_config_path,
            persist_result=persist_result,
            include_case_report=include_case_report,
        )

    @classmethod
    def normalize_request(cls, request: TankenWorkflowRequest) -> TankenWorkflowRequest:
        return cls.build_request(
            case_id=request.case_id,
            event_csv_path=request.event_csv_path,
            reservoir_config_path=request.reservoir_config_path,
            persist_result=request.persist_result,
            include_case_report=request.include_case_report,
        )

    async def _call_mcp_tool(self, tool_name: str, **arguments: Any) -> dict[str, Any]:
        if self._mcp_tools is None:
            raise RuntimeError("MCP tools are not connected")
        try:
            function = self._mcp_tools.functions[tool_name]
        except KeyError as exc:
            raise RuntimeError(f"MCP tool is not available: {tool_name}") from exc

        execution = await FunctionCall(function=function, arguments=arguments).aexecute()
        if execution.status != "success":
            raise RuntimeError(execution.error or f"MCP tool call failed: {tool_name}")

        result = execution.result
        content = getattr(result, "content", result)
        return self._parse_json_payload(content, tool_name=tool_name)

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
    def _request_from_input(step_input: StepInput) -> TankenWorkflowRequest:
        raw = step_input.input
        if raw is None:
            raise ValueError("Workflow input is required")
        return TankenWorkflowRequest.model_validate(raw)

    @staticmethod
    def _base_case_args(request: TankenWorkflowRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {"case_id": request.case_id}
        if request.event_csv_path is not None:
            payload["event_csv_path"] = request.event_csv_path
        if request.reservoir_config_path is not None:
            payload["reservoir_config_path"] = request.reservoir_config_path
        return payload

    async def _describe_case_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        payload = await self._call_mcp_tool("describe_tanken_case", case_id=request.case_id)
        return StepOutput(content=payload)

    async def _get_status_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        payload = await self._call_mcp_tool(
            "get_tanken_case_status",
            **self._base_case_args(request),
        )
        return StepOutput(content=payload)

    async def _get_rules_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        payload = await self._call_mcp_tool(
            "query_tanken_dispatch_rules",
            **self._base_case_args(request),
        )
        return StepOutput(content=payload)

    async def _optimize_plan_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        payload = await self._call_mcp_tool(
            "optimize_tanken_release_plan",
            **self._base_case_args(request),
        )
        return StepOutput(content=payload)

    async def _simulate_plan_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        optimization = step_input.get_step_content("optimize_plan")
        if not isinstance(optimization, dict):
            raise RuntimeError("Missing optimization output for simulate_plan step")

        payload = await self._call_mcp_tool(
            "simulate_tanken_dispatch_program",
            **self._base_case_args(request),
            target_outflow=float(optimization["avg_release_m3s"]),
            module_type=str(optimization["selected_module_type"]),
            module_parameters=dict(optimization["selected_module_parameters"]),
        )
        return StepOutput(content=payload)

    async def _evaluate_plan_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        optimization = step_input.get_step_content("optimize_plan")
        if not isinstance(optimization, dict):
            raise RuntimeError("Missing optimization output for evaluate_plan step")

        payload = await self._call_mcp_tool(
            "evaluate_tanken_dispatch_result",
            **self._base_case_args(request),
            target_outflow=float(optimization["avg_release_m3s"]),
            module_type=str(optimization["selected_module_type"]),
            module_parameters=dict(optimization["selected_module_parameters"]),
        )
        return StepOutput(content=payload)

    async def _run_case_report_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        if not request.include_case_report:
            return StepOutput(content={"skipped": True, "reason": "case_report_disabled"})

        payload = await self._call_mcp_tool(
            "run_tanken_case",
            **self._base_case_args(request),
            persist_result=request.persist_result,
        )
        return StepOutput(content=payload)

    async def _assemble_result_step(self, step_input: StepInput) -> StepOutput:
        request = self._request_from_input(step_input)
        describe_case = step_input.get_step_content("describe_case")
        status = step_input.get_step_content("get_status")
        rules = step_input.get_step_content("get_rules")
        optimization = step_input.get_step_content("optimize_plan")
        simulation = step_input.get_step_content("simulate_plan")
        evaluation = step_input.get_step_content("evaluate_plan")
        case_report = step_input.get_step_content("run_case_report")

        payload = {
            "workflow": {
                "name": self.workflow.name,
                "mode": "deterministic_mcp_steps",
                "mcp_command": self.mcp_command,
            },
            "request": request.model_dump(mode="json"),
            "recommended_step_sequence": None
            if not isinstance(describe_case, dict)
            else describe_case.get("recommended_step_sequence"),
            "describe_case": describe_case,
            "status": status,
            "rules": rules,
            "optimization": optimization,
            "simulation": simulation,
            "evaluation": evaluation,
            "case_report": case_report,
        }
        return StepOutput(content=payload)


def create_tanken_workflow_runner(
    *, mcp_command: str = DEFAULT_TANKEN_MCP_COMMAND
) -> TankenWorkflowRunner:
    return TankenWorkflowRunner(mcp_command=mcp_command)
