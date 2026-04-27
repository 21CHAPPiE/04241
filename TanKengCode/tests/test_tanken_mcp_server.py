from __future__ import annotations

from pathlib import Path

import project.scenario_executor as scenario_executor
from project.tanken_common import DEFAULT_RESERVOIR_CONFIG
from project.tanken_mcp_tools import setup_tanken_mcp_tools
from pyresops.server import build_runtime, register_standard_tools


REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


def _build_tanken_tools() -> dict[str, object]:
    mcp = _FakeMCP()
    setup_tanken_mcp_tools(mcp)
    return mcp.tools


def _event_path(case_id: str) -> str:
    if case_id == "6.4.1":
        return str(REPO_ROOT / "data" / "flood_event" / "2024072617.csv")
    if case_id == "6.4.2":
        return str(REPO_ROOT / "data" / "flood_event" / "2024061623.csv")
    if case_id == "6.4.3":
        return str(REPO_ROOT / "data" / "2024072617_with_pred.csv")
    return str(REPO_ROOT / "data" / "flood_event" / "2024061623.csv")


def test_tanken_server_registers_core_and_project_tools(tmp_path: Path) -> None:
    mcp = _FakeMCP()
    runtime = build_runtime(
        reservoir_config_path=str(DEFAULT_RESERVOIR_CONFIG),
        data_dir=tmp_path / "data",
    )

    register_standard_tools(mcp, runtime)
    setup_tanken_mcp_tools(mcp)

    assert "get_reservoir_snapshot" in mcp.tools
    assert "simulate_program" in mcp.tools
    assert "optimize_release_plan" in mcp.tools
    assert "list_tanken_cases" in mcp.tools
    assert "run_tanken_case" in mcp.tools


def test_tanken_case_discovery_tools_surface_recommended_sequence() -> None:
    tools = _build_tanken_tools()

    listed = tools["list_tanken_cases"]()
    described = tools["describe_tanken_case"]("6.4.3")

    assert listed["count"] == 4
    assert listed["recommended_step_sequence"] == [
        "get_tanken_case_status",
        "query_tanken_dispatch_rules",
        "optimize_tanken_release_plan",
        "simulate_tanken_dispatch_program",
        "evaluate_tanken_dispatch_result",
    ]
    assert described["case_id"] == "6.4.3"
    assert described["prediction_column"] == "predict"


def test_tanken_step_tools_execute_fixed_chain_for_case_641() -> None:
    tools = _build_tanken_tools()
    event_csv_path = _event_path("6.4.1")

    status = tools["get_tanken_case_status"]("6.4.1", event_csv_path=event_csv_path)
    rules = tools["query_tanken_dispatch_rules"]("6.4.1", event_csv_path=event_csv_path)
    optimization = tools["optimize_tanken_release_plan"]("6.4.1", event_csv_path=event_csv_path)
    simulation = tools["simulate_tanken_dispatch_program"](
        "6.4.1",
        target_outflow=float(optimization["avg_release_m3s"]),
        module_type=str(optimization["selected_module_type"]),
        module_parameters=dict(optimization["selected_module_parameters"]),
        event_csv_path=event_csv_path,
    )
    evaluation = tools["evaluate_tanken_dispatch_result"](
        "6.4.1",
        target_outflow=float(optimization["avg_release_m3s"]),
        module_type=str(optimization["selected_module_type"]),
        module_parameters=dict(optimization["selected_module_parameters"]),
        event_csv_path=event_csv_path,
    )

    assert status["scenario_id"] == "6.4.1"
    assert rules["target_level_m"] == 156.5
    assert optimization["selected_module_type"]
    assert simulation["module_type"] == optimization["selected_module_type"]
    assert evaluation["overall_score"] >= 0


def test_run_tanken_case_exposes_case_specific_evidence() -> None:
    tools = _build_tanken_tools()

    plan_compare = tools["run_tanken_case"]("6.4.2", event_csv_path=_event_path("6.4.2"))
    dynamic_update = tools["run_tanken_case"]("6.4.3", event_csv_path=_event_path("6.4.3"))
    emergency = tools["run_tanken_case"]("6.4.4", event_csv_path=_event_path("6.4.4"))

    assert "saved_path" not in plan_compare
    assert plan_compare["candidate_plans"][0]["downstream_safety"]["safe"] in {True, False}
    assert dynamic_update["simulation_evidence"]["stages"][1]["instruction_delta"]["change_type"] == "incremental_update"
    assert emergency["decision_summary"]["current_disposal_level"] == "162.84m-163.54m"


def test_run_all_tanken_cases_defaults_to_in_memory_results() -> None:
    tools = _build_tanken_tools()

    payload = tools["run_all_tanken_cases"]()

    assert set(payload.keys()) == {"6.4.1", "6.4.2", "6.4.3", "6.4.4"}
    assert all("saved_path" not in case_payload for case_payload in payload.values())


def test_run_tanken_case_can_persist_results_when_requested(
    monkeypatch,
    tmp_path: Path,
) -> None:
    tools = _build_tanken_tools()
    monkeypatch.setattr(scenario_executor, "RESULTS_DIR", tmp_path / "results")

    payload = tools["run_tanken_case"](
        "6.4.1",
        event_csv_path=_event_path("6.4.1"),
        persist_result=True,
    )

    assert "saved_path" in payload
    assert Path(payload["saved_path"]).exists()
