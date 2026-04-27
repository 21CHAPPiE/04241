from __future__ import annotations

from pathlib import Path

from project.tanken import build_tanken_runtime_scenario, run_tanken_demo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_tanken_runtime_scenario_uses_3h_event_step() -> None:
    scenario = build_tanken_runtime_scenario(
        case_id="6.4.1",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024072617.csv",
    )

    assert scenario["time_step_hours"] == 3
    assert len(scenario["benchmark_inflow_series_m3s"]) == 8
    assert scenario["current_level"] == 157.5
    assert scenario["event_summary"]["time_step_hours_median"] == "3.00"


def test_run_tanken_pre_release_outputs_alerts_and_recommended_plan() -> None:
    payload = run_tanken_demo(
        case_id="6.4.1",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024072617.csv",
        save_result=False,
    )

    assert payload["decision_summary"]["target_control_level_m"] == 156.5
    assert payload["candidate_plans"][1]["name"] == "recommended_pre_release_plan"
    assert isinstance(payload["alerts"], list)
    assert payload["data_time_step_hours"] == 3


def test_run_tanken_plan_compare_outputs_three_candidates() -> None:
    payload = run_tanken_demo(
        case_id="6.4.2",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024061623.csv",
        save_result=False,
    )

    assert payload["decision_summary"]["recommended_plan"].startswith("Plan ")
    assert len(payload["candidate_plans"]) == 3
    assert {item["name"] for item in payload["candidate_plans"]} == {
        "Plan A - Conservative",
        "Plan B - Balanced",
        "Plan C - Constraint-first",
    }


def test_run_tanken_dynamic_update_outputs_incremental_delta() -> None:
    payload = run_tanken_demo(
        case_id="6.4.3",
        event_csv_path=REPO_ROOT / "data" / "2024072617_with_pred.csv",
        save_result=False,
    )

    stages = payload["simulation_evidence"]["stages"]
    assert len(stages) == 3
    assert stages[1]["instruction_delta"]["change_type"] == "incremental_update"
    assert payload["instruction_delta"]["current_stage"] == "T2"
    assert payload["rule_context"]["chosen_flood_event"] == "2024072617_with_pred.csv"
    assert stages[0]["forecast_error_summary"]["paired_points"] == 8


def test_run_tanken_emergency_outputs_island_rule_band() -> None:
    payload = run_tanken_demo(
        case_id="6.4.4",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024061623.csv",
        save_result=False,
    )

    assert payload["rule_context"]["communication_status"] == "isolated"
    assert payload["decision_summary"]["current_disposal_level"] == "162.84m-163.54m"
    assert payload["alerts"][0]["triggered"] is True
