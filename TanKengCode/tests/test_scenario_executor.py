from __future__ import annotations

from pathlib import Path

from project.scenario_executor import execute_all_cases, execute_case


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_execute_case_runs_plan_compare_without_saving() -> None:
    payload = execute_case(
        case_id="6.4.2",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024061623.csv",
        save_result=False,
    )

    assert payload["case_id"] == "6.4.2"
    assert payload["kind"] == "plan_compare"
    assert payload["decision_summary"]["recommended_plan"]


def test_execute_all_cases_returns_all_known_cases_without_saving() -> None:
    payload = execute_all_cases(save_result=False)

    assert set(payload.keys()) == {"6.4.1", "6.4.2", "6.4.3", "6.4.4"}
