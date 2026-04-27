from __future__ import annotations

import asyncio

from project.agents.tanken_workflow import create_tanken_workflow_runner


def _run_workflow(case_id: str, *, include_case_report: bool = True):
    runner = create_tanken_workflow_runner()
    request = runner.build_request(
        case_id=case_id,
        include_case_report=include_case_report,
    )
    result = asyncio.run(runner.run(request))
    return result.content


def test_agno_workflow_runs_case_641_via_mcp() -> None:
    payload = _run_workflow("6.4.1")

    assert payload["workflow"]["mode"] == "deterministic_mcp_steps"
    assert payload["status"]["scenario_id"] == "6.4.1"
    assert payload["rules"]["target_level_m"] == 156.5
    assert payload["optimization"]["selected_module_type"]
    assert payload["simulation"]["module_type"] == payload["optimization"]["selected_module_type"]
    assert payload["evaluation"]["overall_score"] >= 0
    assert payload["case_report"]["decision_summary"]["target_control_level_m"] == 156.5


def test_agno_workflow_runs_case_642_via_mcp() -> None:
    payload = _run_workflow("6.4.2")

    assert payload["status"]["scenario_id"] == "6.4.2"
    assert payload["case_report"]["decision_summary"]["recommended_plan"].startswith("Plan ")
    assert len(payload["case_report"]["candidate_plans"]) == 3
    assert "downstream_safety" in payload["case_report"]["candidate_plans"][0]


def test_agno_workflow_surfaces_dynamic_update_case_report() -> None:
    payload = _run_workflow("6.4.3")

    assert payload["case_report"]["rule_context"]["chosen_flood_event"] == "2024072617_with_pred.csv"
    assert payload["case_report"]["simulation_evidence"]["stages"][1]["instruction_delta"]["change_type"] == (
        "incremental_update"
    )


def test_agno_workflow_runs_case_644_via_mcp() -> None:
    payload = _run_workflow("6.4.4")

    assert payload["status"]["scenario_id"] == "6.4.4"
    assert payload["case_report"]["rule_context"]["communication_status"] == "isolated"
    assert payload["case_report"]["decision_summary"]["current_disposal_level"] == "162.84m-163.54m"


def test_agno_workflow_can_skip_case_report_step() -> None:
    payload = _run_workflow("6.4.2", include_case_report=False)

    assert payload["case_report"] == {"skipped": True, "reason": "case_report_disabled"}
    assert payload["optimization"]["selected_module_type"]
    assert payload["evaluation"]["overall_score"] >= 0


def test_agno_workflow_can_run_all_cases() -> None:
    runner = create_tanken_workflow_runner()
    payload = asyncio.run(runner.run_all_cases())

    assert payload["workflow"]["mode"] == "deterministic_mcp_steps_batch"
    assert payload["case_ids"] == ["6.4.1", "6.4.2", "6.4.3", "6.4.4"]
    assert set(payload["results"].keys()) == {"6.4.1", "6.4.2", "6.4.3", "6.4.4"}
    assert payload["results"]["6.4.1"]["case_report"]["decision_summary"]["target_control_level_m"] == 156.5
    assert payload["results"]["6.4.2"]["case_report"]["decision_summary"]["recommended_plan"].startswith("Plan ")
    assert payload["results"]["6.4.3"]["case_report"]["instruction_delta"]["current_stage"] == "T2"
    assert payload["results"]["6.4.4"]["case_report"]["decision_summary"]["current_disposal_level"] == (
        "162.84m-163.54m"
    )
