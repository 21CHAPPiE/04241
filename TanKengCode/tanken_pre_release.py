from __future__ import annotations

from typing import Any

from .tanken_common import (
    build_input_snapshot,
    load_json_payload,
    make_tools,
    run_fixed_chain,
    run_report_plugin,
    todo_gaps,
)
from .tanken_rules_bridge import resolve_alert_payload, resolve_pre_release_decision


def run_baseline_simulation(scenario: dict[str, Any], current_outflow_m3s: float) -> dict[str, Any]:
    tools = make_tools(scenario)
    return load_json_payload(
        tools["simulate_dispatch_program"](
            scenario_id=scenario["id"],
            target_outflow=float(current_outflow_m3s),
            module_type="constant_release",
        )
    )


def build_pre_release_report(scenario: dict[str, Any]) -> dict[str, Any]:
    stage_context = scenario["stage_context"]
    current_outflow = float(scenario["initial_outflow"])
    baseline = run_baseline_simulation(scenario, current_outflow)
    chain = run_fixed_chain(scenario)
    predicted_max_level = float(baseline["max_level_m"])
    current_level = float(scenario["current_level"])
    control_level = float(stage_context["control_level_m"])
    trigger_payload = resolve_pre_release_decision(
        current_level_m=current_level,
        predicted_max_level_m=predicted_max_level,
        stage_context=stage_context,
        weather_signal=scenario["weather_signal"],
    )
    trigger = bool(trigger_payload.get("should_pre_release", False))
    alerts = [
        resolve_alert_payload(
            "high_water",
            current_level_m=current_level,
            predicted_max_level_m=predicted_max_level,
            stage_context=stage_context,
            should_pre_release=trigger,
        ),
        resolve_alert_payload(
            "release_warning",
            current_level_m=current_level,
            predicted_max_level_m=predicted_max_level,
            stage_context=stage_context,
            should_pre_release=trigger,
        ),
    ]
    trigger_reason = (
        f"baseline predicted max level {predicted_max_level:.3f}m exceeds control level {control_level:.3f}m"
        if trigger_payload.get("trigger_reason") == "predicted_max_exceeds_control_level"
        else (
            "transition stage with severe weather requires pre-release"
            if trigger_payload.get("trigger_reason") == "transition_with_severe_weather"
            else f"baseline predicted max level {predicted_max_level:.3f}m does not exceed control level {control_level:.3f}m"
        )
    )
    return run_report_plugin(
        case_id="6.4.1",
        metadata={
            "scenario": scenario,
            "input_snapshot": build_input_snapshot(scenario),
            "stage_context": stage_context,
            "baseline": baseline,
            "chain": chain,
            "trigger_payload": trigger_payload,
            "trigger_reason": trigger_reason,
            "alerts": alerts,
            "todo_gaps": todo_gaps("6.4.1"),
        },
    )
