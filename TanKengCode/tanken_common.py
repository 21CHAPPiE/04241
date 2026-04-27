from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from data.summarize_flood_events import compute_step_hours, load_event_rows, summarize_event
from pyresops.plugins import (
    PluginManager,
    PluginSelectionConfig,
    PostPluginContext,
    ReportPluginContext,
)
from pyresops.tools.common import build_simulation_result_from_outflow_payload

from .plugin_runtime import build_project_plugin_manager, build_project_tool_runtime, get_case_workflow, load_project_bootstrap
from .plugins import inspect_csv_file
from .tanken_config import TANKEN_CASES
from .tanken_rules_bridge import load_global_defaults, resolve_stage_context
from .utils.config_loader import load_yaml_file
from .utils.event_io import (
    benchmark_source,
    clean_numeric_series,
    detect_weather_signal,
    estimate_interval_flow_series,
    read_raw_csv_rows,
    resolve_event_path,
)


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_RESERVOIR_CONFIG = PROJECT_DIR / "configs" / "default_reservoir.yaml"
RESULTS_DIR = PROJECT_DIR / "results"


def load_reservoir_config(path: str | Path) -> dict[str, Any]:
    return load_yaml_file(Path(path))


def build_tanken_runtime_scenario(
    *,
    case_id: str,
    event_csv_path: str | Path | None = None,
    reservoir_config_path: str | Path = DEFAULT_RESERVOIR_CONFIG,
    rows_override: list[Any] | None = None,
    level_override_m: float | None = None,
) -> dict[str, Any]:
    case = TANKEN_CASES[case_id]
    global_defaults = load_global_defaults()
    resolved_reservoir_config_path = Path(reservoir_config_path).resolve()
    bootstrap = load_project_bootstrap(str(resolved_reservoir_config_path))
    spec = bootstrap.spec.model_copy(
        deep=True,
        update={"flood_limit_level": float(case.flood_limit_level_m)},
    )
    resolved_event_path = resolve_event_path(event_csv_path, case)
    validation = inspect_csv_file(resolved_event_path, clean_blank_lines=False)
    rows, load_warnings = load_event_rows(resolved_event_path)
    raw_rows = read_raw_csv_rows(resolved_event_path)
    if rows_override is not None:
        rows = rows_override
    rows = rows[: case.max_event_points]
    raw_rows = raw_rows[: len(rows)]
    if not rows:
        raise ValueError(f"No valid event rows loaded from {resolved_event_path}")

    step_hours = compute_step_hours(rows) or 3.0
    step_hours_int = max(1, int(round(step_hours)))
    observed_inflow_series = clean_numeric_series([row.inflow for row in rows])
    outflow_series = clean_numeric_series(
        [row.outflow for row in rows],
        fallback=observed_inflow_series[0] if observed_inflow_series else 0.0,
    )
    prediction_column = case.prediction_column or "predict"
    has_predict = any((raw.get(prediction_column) or "").strip() for raw in raw_rows)
    forecast_inflow_series = (
        clean_numeric_series(
            [
                None
                if (raw.get(prediction_column) or "").strip() == ""
                else float(str(raw[prediction_column]).strip())
                for raw in raw_rows
            ],
            fallback=observed_inflow_series[0] if observed_inflow_series else 0.0,
        )
        if has_predict
        else list(observed_inflow_series)
    )
    planning_inflow_series = (
        list(forecast_inflow_series)
        if case.case_id == "6.4.3" and has_predict
        else list(observed_inflow_series)
    )
    summary, summary_warnings = summarize_event(resolved_event_path, peak_ratio=0.5)
    weather_signal = detect_weather_signal(rows)
    stage_context = resolve_stage_context(rows[0].timestamp, weather_signal)
    initial_level = (
        float(level_override_m)
        if level_override_m is not None
        else float(case.initial_level_m)
    )
    initial_storage = float(spec.level_storage_curve.get_storage(initial_level))

    return {
        "id": case.case_id,
        "name": case.section_title,
        "description": case.description,
        "current_level": initial_level,
        "initial_storage": initial_storage,
        "initial_inflow": observed_inflow_series[0],
        "initial_outflow": outflow_series[0],
        "inflow": planning_inflow_series[0],
        "benchmark_inflow_series_m3s": planning_inflow_series,
        "observed_inflow_series_m3s": observed_inflow_series,
        "forecast_inflow_series_m3s": forecast_inflow_series,
        "prediction_available": has_predict,
        "start_time": rows[0].timestamp.isoformat(sep=" "),
        "benchmark_start_time": rows[0].timestamp,
        "benchmark_interval_flows_m3s": estimate_interval_flow_series(rows, case.season),
        "benchmark_source_markdown": benchmark_source(case),
        "benchmark_preferred_modules": list(case.preferred_modules),
        "flood_limit_level": float(case.flood_limit_level_m),
        "season": case.season,
        "flood_risk": case.flood_risk,
        "time_step_hours": step_hours_int,
        "duration_hours": step_hours_int * len(planning_inflow_series),
        "target_level": float(
            case.target_level_m
            if case.target_level_m is not None
            else stage_context["control_level_m"]
        ),
        "downstream_limit": case.downstream_limit_m3s,
        "constraints": {
            "ecological_min_flow": float(global_defaults.get("eco_min_flow_m3s", 50.0)),
            **(
                {}
                if case.downstream_limit_m3s is None
                else {"downstream_flow_limit": float(case.downstream_limit_m3s)}
            ),
            **(
                {}
                if case.max_level_m is None
                else {"max_level": float(case.max_level_m)}
            ),
        },
        "task_constraints": {
            "target_level": float(
                case.target_level_m
                if case.target_level_m is not None
                else stage_context["control_level_m"]
            ),
            "target_tolerance": 0.3 if case.kind != "plan_compare" else 0.5,
        },
        "objectives": {
            "target_level": float(
                case.target_level_m
                if case.target_level_m is not None
                else stage_context["control_level_m"]
            )
        },
        "event_file": str(resolved_event_path),
        "event_summary": summary,
        "weather_signal": weather_signal,
        "stage_context": stage_context,
        "prediction_column": prediction_column if has_predict else None,
        "global_defaults": global_defaults,
        "reservoir_bootstrap": bootstrap,
        "reservoir_spec": spec,
        "reservoir_config": load_reservoir_config(reservoir_config_path),
        "resolved_reservoir_config_path": str(resolved_reservoir_config_path),
        "input_warnings": [msg.message for msg in validation.messages]
        + load_warnings
        + summary_warnings,
    }


def make_tools(scenario: dict[str, Any]) -> dict[str, Any]:
    runtime = build_project_tool_runtime(scenario)
    return runtime.make_tools()


def load_json_payload(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(value)


def build_timestamps_from_scenario(scenario: dict[str, Any], count: int) -> list[str]:
    start = scenario["benchmark_start_time"]
    step_hours = int(scenario["time_step_hours"])
    return [
        (start + timedelta(hours=step_hours * index)).isoformat()
        for index in range(count)
    ]


def build_outflow_payload(
    scenario: dict[str, Any],
    release_series: list[float],
) -> dict[str, Any]:
    return {
        "timestamps": build_timestamps_from_scenario(scenario, len(release_series)),
        "values": [float(value) for value in release_series],
    }


def build_post_plugin_selection(case_id: str, scenario: dict[str, Any]) -> PluginSelectionConfig | None:
    workflow = get_case_workflow(case_id)
    payload = workflow.get("post_plugin")
    if not isinstance(payload, dict):
        return None
    config = dict(payload.get("config", {}))
    config["interval_flow_series"] = list(scenario.get("benchmark_interval_flows_m3s", []))
    config["dt_hours"] = float(scenario["time_step_hours"])
    config["safe_flow"] = float(
        scenario.get("downstream_limit")
        or scenario["global_defaults"].get("downstream_safe_flow_m3s", 14000.0)
    )
    return PluginSelectionConfig(name=str(payload["name"]), config=config)


def run_post_plugin_for_release_series(
    *,
    case_id: str,
    scenario: dict[str, Any],
    release_series: list[float],
    program_id: str,
    initial_flow: float,
) -> dict[str, Any] | None:
    selection = build_post_plugin_selection(case_id, scenario)
    if selection is None:
        return None
    selection = selection.model_copy(
        update={"config": {**selection.config, "initial_flow": float(initial_flow)}}
    )
    manager: PluginManager = build_project_plugin_manager()
    simulation_result = build_simulation_result_from_outflow_payload(
        program_id=program_id,
        outflow_data=build_outflow_payload(scenario, release_series),
        reference_state=None,
    )
    result = manager.execute_post(
        selection=selection,
        context=PostPluginContext(simulation_result=simulation_result),
    )
    return None if result is None else result.payload


def build_report_plugin_selection(case_id: str) -> PluginSelectionConfig:
    workflow = get_case_workflow(case_id)
    payload = workflow.get("report_plugin")
    if not isinstance(payload, dict):
        raise ValueError(f"Missing report_plugin config for case {case_id}")
    return PluginSelectionConfig(
        name=str(payload["name"]),
        config=dict(payload.get("config", {})),
    )


def run_report_plugin(
    *,
    case_id: str,
    metadata: dict[str, Any],
    report_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manager: PluginManager = build_project_plugin_manager()
    selection = build_report_plugin_selection(case_id)
    result = manager.execute_report(
        selection=selection,
        context=ReportPluginContext(
            metadata=metadata,
            report_options=report_options or {},
        ),
    )
    if result is None:
        raise RuntimeError(f"Report plugin returned no result for case {case_id}")
    return dict(result.payload["report"])


def run_fixed_chain(scenario: dict[str, Any]) -> dict[str, Any]:
    tools = make_tools(scenario)
    scenario_id = scenario["id"]
    status = load_json_payload(tools["get_reservoir_status"](scenario_id))
    rules = load_json_payload(tools["query_dispatch_rules"](scenario_id))
    optimization = load_json_payload(tools["optimize_release_plan"](scenario_id))
    simulation = load_json_payload(
        tools["simulate_dispatch_program"](
            scenario_id=scenario_id,
            target_outflow=float(optimization["avg_release_m3s"]),
            module_type=str(optimization["selected_module_type"]),
            module_parameters_json=json.dumps(
                optimization["selected_module_parameters"], ensure_ascii=False
            ),
        )
    )
    evaluation = load_json_payload(
        tools["evaluate_dispatch_result"](
            scenario_id=scenario_id,
            target_outflow=float(optimization["avg_release_m3s"]),
            module_type=str(optimization["selected_module_type"]),
            module_parameters_json=json.dumps(
                optimization["selected_module_parameters"], ensure_ascii=False
            ),
        )
    )
    return {
        "status": status,
        "rules": rules,
        "optimization": optimization,
        "simulation": simulation,
        "evaluation": evaluation,
    }


def build_input_snapshot(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": scenario["id"],
        "event_file": scenario["event_file"],
        "start_time": scenario["event_summary"]["start_time"],
        "time_step_hours": scenario["time_step_hours"],
        "record_count": len(scenario["benchmark_inflow_series_m3s"]),
        "current_level_m": scenario["current_level"],
        "initial_storage_billion_m3": round(float(scenario["initial_storage"]), 4),
        "initial_inflow_m3s": scenario["initial_inflow"],
        "initial_outflow_m3s": scenario["initial_outflow"],
        "level_source": "case_override_for_demo",
    }


def todo_gaps(case_id: str) -> list[str]:
    shared = [
        "Cases 6.4.1, 6.4.2, and 6.4.4 still rely on historical flood processes as forecast-proxy inputs."
    ]
    if case_id == "6.4.3":
        return shared + ["Only one forecast-enabled sample is currently connected: 2024072617_with_pred.csv."]
    if case_id == "6.4.2":
        return shared + ["Hecheng interval inflow is still estimated heuristically in project scope."]
    return shared
