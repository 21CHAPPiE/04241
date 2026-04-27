from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .tanken_common import DEFAULT_RESERVOIR_CONFIG, RESULTS_DIR, build_tanken_runtime_scenario
from .tanken_config import TANKEN_CASES, TankenCase
from .tanken_dynamic_update import build_dynamic_update_report
from .tanken_emergency import build_emergency_report
from .tanken_plan_compare import build_plan_compare_report
from .tanken_pre_release import build_pre_release_report


ScenarioBuilder = Callable[..., dict[str, Any]]


def build_case_report_path(results_dir: Path, case_id: str) -> Path:
    return results_dir / f"{case_id.replace('.', '_')}_report.json"


def build_report_path(results_dir: Path, name: str) -> Path:
    return results_dir / name


def save_case_payload(results_dir: Path, case_id: str, payload: dict[str, Any]) -> str:
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = build_case_report_path(results_dir, case_id)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def load_saved_case_reports(results_dir: Path, case_ids: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return {
        case_id: json.loads(build_case_report_path(results_dir, case_id).read_text(encoding="utf-8"))
        for case_id in case_ids
    }


def _build_pre_release_case(
    *,
    case: TankenCase,
    event_csv_path: str | Path | None,
    reservoir_config_path: str | Path,
) -> dict[str, Any]:
    scenario = build_tanken_runtime_scenario(
        case_id=case.case_id,
        event_csv_path=event_csv_path,
        reservoir_config_path=reservoir_config_path,
    )
    return build_pre_release_report(scenario)


def _build_plan_compare_case(
    *,
    case: TankenCase,
    event_csv_path: str | Path | None,
    reservoir_config_path: str | Path,
) -> dict[str, Any]:
    scenario = build_tanken_runtime_scenario(
        case_id=case.case_id,
        event_csv_path=event_csv_path,
        reservoir_config_path=reservoir_config_path,
    )
    return build_plan_compare_report(scenario)


def _build_emergency_case(
    *,
    case: TankenCase,
    event_csv_path: str | Path | None,
    reservoir_config_path: str | Path,
) -> dict[str, Any]:
    scenario = build_tanken_runtime_scenario(
        case_id=case.case_id,
        event_csv_path=event_csv_path,
        reservoir_config_path=reservoir_config_path,
    )
    return build_emergency_report(scenario)


def _build_dynamic_update_case(
    *,
    case: TankenCase,
    event_csv_path: str | Path | None,
    reservoir_config_path: str | Path,
) -> dict[str, Any]:
    return build_dynamic_update_report(
        case,
        str(event_csv_path) if event_csv_path is not None else None,
        str(reservoir_config_path),
    )


SCENARIO_BUILDERS: dict[str, ScenarioBuilder] = {
    "pre_release": _build_pre_release_case,
    "plan_compare": _build_plan_compare_case,
    "dynamic_update": _build_dynamic_update_case,
    "emergency_island": _build_emergency_case,
}


def execute_case(
    *,
    case_id: str,
    event_csv_path: str | Path | None = None,
    reservoir_config_path: str | Path = DEFAULT_RESERVOIR_CONFIG,
    save_result: bool = True,
) -> dict[str, Any]:
    case = TANKEN_CASES[case_id]
    try:
        builder = SCENARIO_BUILDERS[case.kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported Tanken case kind: {case.kind}") from exc

    report = builder(
        case=case,
        event_csv_path=event_csv_path,
        reservoir_config_path=reservoir_config_path,
    )
    payload = {
        "case_id": case.case_id,
        "section_title": case.section_title,
        "kind": case.kind,
        **report,
    }
    if save_result:
        payload["saved_path"] = save_case_payload(RESULTS_DIR, case_id, payload)
    return payload


def execute_all_cases(
    *,
    reservoir_config_path: str | Path = DEFAULT_RESERVOIR_CONFIG,
    save_result: bool = True,
) -> dict[str, dict[str, Any]]:
    return {
        case_id: execute_case(
            case_id=case_id,
            reservoir_config_path=reservoir_config_path,
            save_result=save_result,
        )
        for case_id in TANKEN_CASES
    }


def build_execution_markdown(
    reports: dict[str, dict[str, Any]],
    *,
    workflow_verification: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = [
        "# Tanken 6.4 Execution Summary",
        "",
        "## Run Overview",
        "",
        "- Command: `python project/run_tanken_demo.py all`",
        "- Tests: `python -m pytest project/tests`",
        "- Result directory: `project/results/`",
        "",
        "## Core Execution Flow",
        "",
        "All scenarios now run through the same project execution path:",
        "",
        "1. Load reservoir bootstrap through the provider layer.",
        "2. Build the runtime scenario from case config, event rows, and rule context.",
        "3. Execute the in-process tool chain:",
        "   - `get_reservoir_status`",
        "   - `query_dispatch_rules`",
        "   - `optimize_release_plan`",
        "   - `simulate_dispatch_program`",
        "   - `evaluate_dispatch_result`",
        "4. Apply project post/report plugins when configured.",
        "5. Save per-case JSON and regenerate the summary report.",
        "",
        "## Workflow Verification",
        "",
        "The deterministic Agno workflow now drives the same fixed MCP chain through the project-local entrypoint:",
        "",
        "- Workflow command: `pyresops-tanken-workflow --case-id 6.4.1`",
        "- Batch workflow command: `pyresops-tanken-workflow --case-id all`",
        "- Internal MCP command: `uv run python -m project.tanken_mcp_server`",
        "- Workflow tests: `uv run pytest project/tests/test_tanken_agno_workflow.py project/tests/test_tanken_mcp_server.py -q`",
        "",
    ]

    if workflow_verification is not None:
        verification_date = workflow_verification.get("verification_date")
        if verification_date:
            lines.extend(
                [
                    f"- Verified on: `{verification_date}`",
                    "",
                ]
            )
        for item in workflow_verification.get("checks", []):
            lines.append(f"- `{item['command']}`: `{item['status']}`")
        lines.append("")

    lines.extend(
        [
            "## Scenario Table",
            "",
            "| Case | Input file | Step hours | Main conclusion |",
            "| --- | --- | ---: | --- |",
        ]
    )

    for case_id in ("6.4.1", "6.4.2", "6.4.3", "6.4.4"):
        payload = reports[case_id]
        input_snapshot = payload["input_snapshot"]
        if case_id == "6.4.1":
            conclusion = (
                f"Pre-release triggered, target level {payload['decision_summary']['target_control_level_m']} m, "
                f"recommended release {payload['candidate_plans'][1]['declared_outflow_m3s']} m3/s"
            )
        elif case_id == "6.4.2":
            conclusion = (
                f"Recommended {payload['decision_summary']['recommended_plan']}, "
                f"release {payload['decision_summary']['recommended_outflow_m3s']} m3/s"
            )
        elif case_id == "6.4.3":
            conclusion = (
                f"{payload['decision_summary']['version_count']} rolling updates, "
                f"final release {payload['decision_summary']['final_recommended_outflow_m3s']} m3/s"
            )
        else:
            conclusion = (
                f"Emergency band {payload['decision_summary']['current_disposal_level']}, "
                f"cap {payload['decision_summary']['recommended_outflow_cap_m3s']} m3/s"
            )
        lines.append(
            f"| {case_id} | `{Path(input_snapshot['event_file']).name}` | "
            f"{payload['data_time_step_hours']} | {conclusion} |"
        )

    for case_id in ("6.4.1", "6.4.2", "6.4.3", "6.4.4"):
        payload = reports[case_id]
        lines.extend(["", f"## {case_id} {payload['section_title']}", ""])
        lines.append(f"- Input file: `{payload['input_snapshot']['event_file']}`")
        lines.append(f"- Current level: `{payload['input_snapshot']['current_level_m']}` m")
        lines.append(f"- Step size: `{payload['data_time_step_hours']}` h")
        lines.append("- Tool chain: `status -> rules -> optimize -> simulate -> evaluate`")

        if case_id == "6.4.1":
            lines.append(f"- Pre-release triggered: `{payload['decision_summary']['should_pre_release']}`")
            lines.append(f"- Target control level: `{payload['decision_summary']['target_control_level_m']}` m")
            lines.append(
                f"- Recommended release: `{payload['candidate_plans'][1]['declared_outflow_m3s']}` m3/s, "
                f"overall score `{payload['candidate_plans'][1]['overall_score']}`"
            )
            lines.append(
                f"- Baseline final level: `{payload['candidate_plans'][0]['predicted_final_level_m']}` m, "
                f"recommended final level: `{payload['candidate_plans'][1]['predicted_final_level_m']}` m"
            )
        elif case_id == "6.4.2":
            lines.append(f"- Recommended plan: `{payload['decision_summary']['recommended_plan']}`")
            lines.append(f"- Recommended release: `{payload['decision_summary']['recommended_outflow_m3s']}` m3/s")
            for candidate in payload["candidate_plans"]:
                lines.append(
                    f"- {candidate['name']}: release `{candidate['declared_outflow_m3s']}` m3/s, "
                    f"score `{candidate['evaluation']['overall_score']}`, "
                    f"downstream safe `{candidate['downstream_safety']['safe']}`"
                )
            lines.append("- Post plugin: `tanken_hecheng_downstream`")
        elif case_id == "6.4.3":
            lines.append(f"- Forecast case: `{payload['rule_context']['chosen_flood_event']}`")
            lines.append(f"- Prediction column: `{payload['rule_context']['prediction_column']}`")
            for stage in payload["simulation_evidence"]["stages"]:
                lines.append(
                    f"- {stage['stage']}: window `{stage['selected_plan']['window_points']}`, "
                    f"release `{stage['selected_plan']['recommended_outflow_m3s']}` m3/s, "
                    f"MAE `{stage['forecast_error_summary']['mean_abs_error_m3s']}` m3/s, "
                    f"instruction delta `{stage['instruction_delta']['summary']}`"
                )
            lines.append("- Report plugin: `tanken_forecast_error_summary` + `tanken_case_report`")
        else:
            candidate = payload["candidate_plans"][0]
            lines.append(f"- Emergency band: `{payload['decision_summary']['current_disposal_level']}`")
            lines.append(f"- Recommended release: `{candidate['declared_outflow_m3s']}` m3/s")
            lines.append(
                f"- Downstream safe: `{candidate['downstream_safety']['safe']}`, "
                f"max downstream flow `{candidate['downstream_safety']['max_flow']}` m3/s"
            )
            lines.append(
                f"- Constraint violation count: `{candidate['evaluation']['constraint_violations_count']}`"
            )
            lines.append("- Post plugin: `tanken_hecheng_downstream`")

        lines.extend(["", "Known gaps:", *[f"- {item}" for item in payload.get("todo_gaps", [])]])

    lines.extend(
        [
            "",
            "## Reliability Note",
            "",
            "- The project flow is reliable enough for internal demonstration and scenario walkthroughs.",
            "- It is not yet strong enough to support strong claims about forecast realism or operational deployment.",
            "- The remaining limitations are listed per case above and should be closed before external delivery.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_execution_report() -> Path:
    execute_all_cases(save_result=True)
    reports = load_saved_case_reports(RESULTS_DIR, ("6.4.1", "6.4.2", "6.4.3", "6.4.4"))
    report_path = build_report_path(RESULTS_DIR, "tanken_execution_report.md")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_execution_markdown(reports), encoding="utf-8")
    return report_path
