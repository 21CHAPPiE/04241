from __future__ import annotations

import json
from typing import Any

from .tanken_common import (
    build_input_snapshot,
    load_json_payload,
    make_tools,
    run_fixed_chain,
    run_post_plugin_for_release_series,
    run_report_plugin,
    todo_gaps,
)
from .tanken_rules_bridge import load_global_defaults, load_plan_compare_templates


def candidate_release_series(
    scenario: dict[str, Any],
    *,
    target_outflow_m3s: float,
    from_optimization: dict[str, Any] | None = None,
) -> list[float]:
    if from_optimization and isinstance(from_optimization.get("release_values_m3s"), list):
        return [float(value) for value in from_optimization["release_values_m3s"]]
    return [float(target_outflow_m3s)] * len(scenario["benchmark_inflow_series_m3s"])


def evaluate_candidate(
    scenario: dict[str, Any],
    *,
    name: str,
    target_outflow_m3s: float,
    module_type: str = "constant_release",
    module_parameters: dict[str, Any] | None = None,
    from_optimization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tools = make_tools(scenario)
    global_defaults = load_global_defaults()
    parameters_json = "" if not module_parameters else json.dumps(module_parameters, ensure_ascii=False)
    simulation = load_json_payload(
        tools["simulate_dispatch_program"](
            scenario_id=scenario["id"],
            target_outflow=float(target_outflow_m3s),
            module_type=module_type,
            module_parameters_json=parameters_json,
        )
    )
    evaluation = load_json_payload(
        tools["evaluate_dispatch_result"](
            scenario_id=scenario["id"],
            target_outflow=float(target_outflow_m3s),
            module_type=module_type,
            module_parameters_json=parameters_json,
        )
    )
    release_series = candidate_release_series(
        scenario,
        target_outflow_m3s=target_outflow_m3s,
        from_optimization=from_optimization,
    )
    downstream_payload = run_post_plugin_for_release_series(
        case_id="6.4.2",
        scenario=scenario,
        release_series=release_series,
        program_id=f"{scenario['id']}_{name}",
        initial_flow=float(target_outflow_m3s),
    ) or {}
    downstream = downstream_payload.get(
        "downstream_safety",
        {
            "safe": True,
            "max_flow": 0.0,
            "safe_flow": float(
                scenario.get("downstream_limit")
                or global_defaults.get("downstream_safe_flow_m3s", 14000.0)
            ),
            "exceedance_count": 0,
            "exceedances": [],
            "max_exceedance": 0.0,
        },
    )
    return {
        "name": name,
        "module_type": module_type,
        "module_parameters": module_parameters or {},
        "declared_outflow_m3s": round(float(target_outflow_m3s), 3),
        "simulation": simulation,
        "evaluation": evaluation,
        "downstream_safety": downstream,
        "plugin_results": downstream_payload,
    }


def build_plan_compare_report(scenario: dict[str, Any]) -> dict[str, Any]:
    global_defaults = load_global_defaults()
    templates = load_plan_compare_templates()
    chain = run_fixed_chain(scenario)
    optimized_release = float(chain["optimization"]["avg_release_m3s"])
    optimized_module = str(chain["optimization"]["selected_module_type"])
    optimized_params = dict(chain["optimization"]["selected_module_parameters"])
    spec = scenario["reservoir_spec"]
    max_discharge = float(spec.discharge_capacity.get_max_discharge(float(scenario["current_level"])))
    conservative = templates["conservative"]
    balanced = templates["balanced"]
    constrained = templates["constrained"]
    conservative_release = min(
        max_discharge,
        max(
            optimized_release * float(conservative["optimized_release_multiplier"]),
            float(scenario["initial_inflow"]) * float(conservative["inflow_multiplier"]),
        ),
    )
    constrained_release = max(
        float(constrained.get("min_release_m3s", global_defaults.get("eco_min_flow_m3s", 50.0))),
        optimized_release * float(constrained["optimized_release_multiplier"]),
    )
    candidates = [
        evaluate_candidate(scenario, name=str(conservative["name"]), target_outflow_m3s=conservative_release),
        evaluate_candidate(
            scenario,
            name=str(balanced["name"]),
            target_outflow_m3s=optimized_release,
            module_type=optimized_module,
            module_parameters=optimized_params,
            from_optimization=chain["optimization"],
        ),
        evaluate_candidate(scenario, name=str(constrained["name"]), target_outflow_m3s=constrained_release),
    ]
    scored = sorted(
        candidates,
        key=lambda item: (
            float(item["evaluation"]["overall_score"]),
            0 if item["downstream_safety"]["safe"] else -1,
        ),
        reverse=True,
    )
    recommended = scored[0]
    rejected = [
        {
            "name": item["name"],
            "reason": (
                "Downstream safety is weaker than the recommended plan"
                if not item["downstream_safety"]["safe"]
                else "Overall score is lower than the recommended plan"
            ),
        }
        for item in scored[1:]
    ]
    return run_report_plugin(
        case_id="6.4.2",
        metadata={
            "scenario": scenario,
            "input_snapshot": build_input_snapshot(scenario),
            "chain": chain,
            "candidate_plans": candidates,
            "recommended": recommended,
            "rejected_plans": rejected,
            "todo_gaps": todo_gaps("6.4.2"),
        },
    )
