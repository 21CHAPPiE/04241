from __future__ import annotations

from typing import Any

from .tanken_common import build_input_snapshot, run_report_plugin, todo_gaps
from .tanken_plan_compare import evaluate_candidate
from .tanken_rules_bridge import resolve_emergency_band


def build_emergency_report(scenario: dict[str, Any]) -> dict[str, Any]:
    band = resolve_emergency_band(float(scenario["current_level"]))
    recommended_outflow = (
        float(scenario["initial_inflow"])
        if band["max_release_m3s"] is None
        else min(float(band["max_release_m3s"]), float(scenario["initial_inflow"]) * 1.4)
    )
    candidate = evaluate_candidate(
        scenario,
        name="Local emergency release plan",
        target_outflow_m3s=recommended_outflow,
    )
    return run_report_plugin(
        case_id="6.4.4",
        metadata={
            "scenario": scenario,
            "input_snapshot": build_input_snapshot(scenario),
            "band": band,
            "candidate": candidate,
            "todo_gaps": todo_gaps("6.4.4"),
        },
    )
