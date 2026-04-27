from __future__ import annotations

from typing import Any

from data.summarize_flood_events import load_event_rows
from pyresops.plugins import PluginManager, PluginSelectionConfig, ReportPluginContext

from .plugin_runtime import build_project_plugin_manager, get_case_workflow
from .tanken_common import (
    build_input_snapshot,
    build_tanken_runtime_scenario,
    resolve_event_path,
    run_fixed_chain,
    run_report_plugin,
    todo_gaps,
)
from .tanken_config import TankenCase


def build_instruction_delta(previous_plan: dict[str, Any] | None, current_plan: dict[str, Any]) -> dict[str, Any]:
    if previous_plan is None:
        return {
            "change_type": "initial",
            "summary": "Initial dispatch instruction generated.",
            "release_delta_m3s": 0.0,
        }
    delta = round(
        float(current_plan["recommended_outflow_m3s"]) - float(previous_plan["recommended_outflow_m3s"]),
        3,
    )
    return {
        "change_type": "incremental_update",
        "summary": (
            "Increase release recommendation"
            if delta > 0
            else (
                "Decrease release recommendation"
                if delta < 0
                else "Keep the current release recommendation"
            )
        ),
        "release_delta_m3s": delta,
        "module_changed": current_plan["module_type"] != previous_plan["module_type"],
        "previous_stage": previous_plan["stage"],
        "current_stage": current_plan["stage"],
    }


def build_forecast_error_summary(scenario: dict[str, Any]) -> dict[str, Any]:
    workflow = get_case_workflow("6.4.3")
    selection_payload = dict(workflow["forecast_error_plugin"])
    selection = PluginSelectionConfig(
        name=str(selection_payload["name"]),
        config=dict(selection_payload.get("config", {})),
    )
    manager: PluginManager = build_project_plugin_manager()
    result = manager.execute_report(
        selection=selection,
        context=ReportPluginContext(
            report_options={
                "observed_inflow_series_m3s": scenario.get("observed_inflow_series_m3s", []),
                "forecast_inflow_series_m3s": scenario.get("forecast_inflow_series_m3s", []),
            }
        ),
    )
    if result is None:
        return {"paired_points": 0}
    return dict(result.payload["forecast_error_summary"])


def build_dynamic_update_report(
    case: TankenCase,
    event_csv_path: str | None,
    reservoir_config_path: str,
) -> dict[str, Any]:
    resolved_event_path = resolve_event_path(event_csv_path, case)
    rows, _warnings = load_event_rows(resolved_event_path)
    rows = rows[: case.max_event_points]
    if len(rows) < max(case.stage_windows):
        raise ValueError("Not enough event rows for dynamic update demo")

    stages: list[dict[str, Any]] = []
    previous_plan: dict[str, Any] | None = None
    previous_level = case.initial_level_m
    last_stage_scenario: dict[str, Any] | None = None
    for index, limit in enumerate(case.stage_windows):
        stage_rows = list(rows[:limit])
        stage_scenario = build_tanken_runtime_scenario(
            case_id=case.case_id,
            event_csv_path=resolved_event_path,
            reservoir_config_path=reservoir_config_path,
            rows_override=stage_rows,
            level_override_m=previous_level,
        )
        chain = run_fixed_chain(stage_scenario)
        current_plan = {
            "stage": f"T{index}",
            "window_points": limit,
            "recommended_outflow_m3s": round(float(chain["optimization"]["avg_release_m3s"]), 3),
            "module_type": chain["optimization"]["selected_module_type"],
            "final_level_m": chain["simulation"]["final_level_m"],
            "overall_score": chain["evaluation"]["overall_score"],
        }
        stages.append(
            {
                "stage": f"T{index}",
                "update_reason": (
                    "Initial dispatch plan generated"
                    if previous_plan is None
                    else "New observations and a larger forecast window triggered re-optimization"
                ),
                "input_snapshot": build_input_snapshot(stage_scenario),
                "forecast_error_summary": build_forecast_error_summary(stage_scenario),
                "selected_plan": current_plan,
                "instruction_delta": build_instruction_delta(previous_plan, current_plan),
                "chain": chain,
            }
        )
        previous_plan = current_plan
        previous_level = float(chain["simulation"]["final_level_m"])
        last_stage_scenario = stage_scenario

    return run_report_plugin(
        case_id="6.4.3",
        metadata={
            "scenario": last_stage_scenario or {},
            "stages": stages,
            "stage_windows": list(case.stage_windows),
            "chosen_flood_event": resolved_event_path.name,
            "todo_gaps": todo_gaps("6.4.3"),
        },
    )
