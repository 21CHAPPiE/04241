from __future__ import annotations

import json
from pathlib import Path

from agents.huadong_workflow import DEFAULT_HUADONG_MCP_COMMAND, HUADONG_SCENARIO_IDS, HuadongWorkflowRequest


def test_huadong_workflow_contract_documents_supported_scenarios(project_root: Path) -> None:
    contract_path = project_root / "results" / "huadong_agno_workflow_io_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))

    assert payload["execution_mode"] == "deterministic_agno_workflow_without_agent"
    assert payload["mcp_command"].endswith("-m app.server")
    assert payload["supported_scenarios"] == list(HUADONG_SCENARIO_IDS)
    assert payload["workflow_input"]["required"] == ["scenario_id"]
    assert payload["single_scenario_output"]["required"] == [
        "workflow",
        "request",
        "scenario_id",
        "scenario_dir",
        "report",
        "steps",
    ]


def test_huadong_workflow_source_does_not_use_agno_agent(project_root: Path) -> None:
    source = (project_root / "agents" / "huadong_workflow.py").read_text(encoding="utf-8")

    assert "agno.agent" not in source
    assert "Agent(" not in source
    assert "Workflow(" in source
    assert "MCPTools(" in source


def test_huadong_workflow_request_defaults_to_results_output_root() -> None:
    request = HuadongWorkflowRequest(scenario_id="6.3.1")

    assert request.output_root == "results/agno-workflow-runs"
    assert request.basin_dataset_path == "data/basin_001_hourly.csv"


def test_huadong_workflow_runtime_capture_contains_intermediate_variables(project_root: Path) -> None:
    capture_path = project_root / "results" / "huadong_workflow_pydantic_io_capture.json"
    payload = json.loads(capture_path.read_text(encoding="utf-8"))

    assert payload["capture_method"] == "python_script_runtime_execution"
    assert payload["llm_generated"] is False
    assert payload["server_command_used_by_capture"].endswith("-m app.server")
    assert set(payload["workflow_runs"]) == set(HUADONG_SCENARIO_IDS)

    quick_run = payload["workflow_runs"]["6.3.1"]
    assert "workflow_request_json" in quick_run
    assert "intermediate_variables_json" in quick_run
    assert "step_outputs_json" in quick_run
    assert "workflow_output_json" in quick_run
    assert quick_run["intermediate_variables_json"]["input_slice"].endswith("input_slice.csv")

    first_call = quick_run["tool_calls"][0]
    assert first_call["step"] == "primary_dataset_profile"
    assert first_call["tool_name"] == "dataset_profile_from_paths"
    assert "arguments_json" in first_call
    assert "response_json" in first_call
    assert first_call["response_json"]["status"] == "completed"
