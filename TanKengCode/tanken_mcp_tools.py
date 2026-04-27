from __future__ import annotations

import json
from typing import Any

from .scenario_executor import execute_all_cases, execute_case
from .tanken_common import DEFAULT_RESERVOIR_CONFIG, build_tanken_runtime_scenario, make_tools
from .tanken_config import TANKEN_CASES, get_tanken_case


RECOMMENDED_STEP_SEQUENCE = [
    "get_tanken_case_status",
    "query_tanken_dispatch_rules",
    "optimize_tanken_release_plan",
    "simulate_tanken_dispatch_program",
    "evaluate_tanken_dispatch_result",
]


def setup_tanken_mcp_tools(mcp_server: Any) -> None:
    """Register Tanken-specific case discovery and execution tools."""

    def _resolve_reservoir_config_path(reservoir_config_path: str | None) -> str:
        return str(DEFAULT_RESERVOIR_CONFIG if reservoir_config_path is None else reservoir_config_path)

    def _build_case_scenario(
        case_id: str,
        *,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        return build_tanken_runtime_scenario(
            case_id=case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=_resolve_reservoir_config_path(reservoir_config_path),
        )

    def _build_case_tools(
        case_id: str,
        *,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        scenario = _build_case_scenario(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )
        return scenario, make_tools(scenario)

    @mcp_server.tool()
    def list_tanken_cases() -> dict[str, Any]:
        """List Tanken demo cases and their workflow metadata."""
        cases = [
            {
                "case_id": case.case_id,
                "section_title": case.section_title,
                "kind": case.kind,
                "description": case.description,
                "default_event": case.default_event,
                "preferred_modules": list(case.preferred_modules),
                "prediction_column": case.prediction_column,
            }
            for case in TANKEN_CASES.values()
        ]
        return {
            "cases": cases,
            "count": len(cases),
            "recommended_step_sequence": list(RECOMMENDED_STEP_SEQUENCE),
        }

    @mcp_server.tool()
    def describe_tanken_case(case_id: str) -> dict[str, Any]:
        """Describe one Tanken case and its recommended execution flow."""
        case = get_tanken_case(case_id)
        return {
            "case_id": case.case_id,
            "section_title": case.section_title,
            "kind": case.kind,
            "description": case.description,
            "default_event": case.default_event,
            "initial_level_m": case.initial_level_m,
            "flood_limit_level_m": case.flood_limit_level_m,
            "target_level_m": case.target_level_m,
            "max_level_m": case.max_level_m,
            "downstream_limit_m3s": case.downstream_limit_m3s,
            "preferred_modules": list(case.preferred_modules),
            "prediction_column": case.prediction_column,
            "recommended_step_sequence": list(RECOMMENDED_STEP_SEQUENCE),
        }

    @mcp_server.tool()
    def get_tanken_case_status(
        case_id: str,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        """Return the current reservoir status for one Tanken case."""
        tools = _build_case_tools(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )[1]
        return tools["get_reservoir_status"](case_id)

    @mcp_server.tool()
    def query_tanken_dispatch_rules(
        case_id: str,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        """Return dispatch rules and constraints for one Tanken case."""
        tools = _build_case_tools(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )[1]
        return tools["query_dispatch_rules"](case_id)

    @mcp_server.tool()
    def optimize_tanken_release_plan(
        case_id: str,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
        horizon_hours: int = 0,
        requested_module_type: str = "",
        min_flow: float = 50.0,
        max_flow: float = 0.0,
        control_interval_seconds: int = 0,
    ) -> dict[str, Any]:
        """Optimize a release plan for one Tanken case."""
        tools = _build_case_tools(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )[1]
        return tools["optimize_release_plan"](
            case_id,
            horizon_hours=horizon_hours,
            requested_module_type=requested_module_type,
            min_flow=min_flow,
            max_flow=max_flow,
            control_interval_seconds=control_interval_seconds,
        )

    @mcp_server.tool()
    def simulate_tanken_dispatch_program(
        case_id: str,
        target_outflow: float,
        module_type: str = "constant_release",
        module_parameters: dict[str, Any] | None = None,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        """Simulate a concrete dispatch program for one Tanken case."""
        tools = _build_case_tools(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )[1]
        return tools["simulate_dispatch_program"](
            scenario_id=case_id,
            target_outflow=target_outflow,
            module_type=module_type,
            module_parameters_json=(
                ""
                if not module_parameters
                else json.dumps(module_parameters, ensure_ascii=False)
            ),
        )

    @mcp_server.tool()
    def evaluate_tanken_dispatch_result(
        case_id: str,
        target_outflow: float,
        module_type: str = "constant_release",
        module_parameters: dict[str, Any] | None = None,
        eco_min_flow: float = 50.0,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate one simulated dispatch result for a Tanken case."""
        tools = _build_case_tools(
            case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=reservoir_config_path,
        )[1]
        return tools["evaluate_dispatch_result"](
            scenario_id=case_id,
            target_outflow=target_outflow,
            eco_min_flow=eco_min_flow,
            module_type=module_type,
            module_parameters_json=(
                ""
                if not module_parameters
                else json.dumps(module_parameters, ensure_ascii=False)
            ),
        )

    @mcp_server.tool()
    def run_tanken_case(
        case_id: str,
        event_csv_path: str | None = None,
        reservoir_config_path: str | None = None,
        persist_result: bool = False,
    ) -> dict[str, Any]:
        """Run one full Tanken case through its project-level workflow."""
        return execute_case(
            case_id=case_id,
            event_csv_path=event_csv_path,
            reservoir_config_path=_resolve_reservoir_config_path(reservoir_config_path),
            save_result=persist_result,
        )

    @mcp_server.tool()
    def run_all_tanken_cases(
        reservoir_config_path: str | None = None,
        persist_result: bool = False,
    ) -> dict[str, dict[str, Any]]:
        """Run all Tanken cases through their project-level workflows."""
        return execute_all_cases(
            reservoir_config_path=_resolve_reservoir_config_path(reservoir_config_path),
            save_result=persist_result,
        )
