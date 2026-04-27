from __future__ import annotations

from pathlib import Path

from project.plugin_runtime import build_project_plugin_manager, get_case_workflow
from project.tanken import run_tanken_demo


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_project_plugin_manager_loads_project_plugins() -> None:
    manager = build_project_plugin_manager()
    plugin_names = {item["plugin_name"] for item in manager.describe_all()}
    assert "tanken_hecheng_downstream" in plugin_names
    assert "tanken_forecast_error_summary" in plugin_names
    assert "tanken_case_report" in plugin_names


def test_case_workflow_yaml_exposes_report_and_post_plugins() -> None:
    workflow = get_case_workflow("6.4.2")
    assert workflow["report_plugin"]["name"] == "tanken_case_report"
    assert workflow["post_plugin"]["name"] == "tanken_hecheng_downstream"


def test_plan_compare_candidate_contains_post_plugin_results() -> None:
    payload = run_tanken_demo(
        case_id="6.4.2",
        event_csv_path=REPO_ROOT / "data" / "flood_event" / "2024061623.csv",
        save_result=False,
    )
    first_candidate = payload["candidate_plans"][0]
    assert "plugin_results" in first_candidate
    assert "downstream_safety" in first_candidate["plugin_results"]
