from __future__ import annotations

from typing import Any

from pyresops.plugins import PluginExecutionResult, PluginStage, ReportPluginBase
from pyresops.plugins.models import BasePluginContext, ReportPluginContext


class ForecastErrorSummaryPlugin(ReportPluginBase):
    """Compute paired forecast-error summaries for staged update reports."""

    plugin_name = "tanken_forecast_error_summary"
    stage = PluginStage.POST_EVALUATION
    summary = "Summarize forecast error metrics for observed/forecast inflow series."
    capability_tags = ["forecast_error", "tanken"]

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return dict(config)

    def validate_inputs(self, context: BasePluginContext) -> None:
        super().validate_inputs(context)
        assert isinstance(context, ReportPluginContext)

    def execute(
        self,
        context: BasePluginContext,
        config: dict[str, Any],
    ) -> PluginExecutionResult:
        self.validate_inputs(context)
        assert isinstance(context, ReportPluginContext)
        observed = [
            float(value) for value in context.report_options.get("observed_inflow_series_m3s", [])
        ]
        forecast = [
            float(value) for value in context.report_options.get("forecast_inflow_series_m3s", [])
        ]
        count = min(len(observed), len(forecast))
        if count == 0:
            summary = {"paired_points": 0}
        else:
            abs_errors = [abs(forecast[idx] - observed[idx]) for idx in range(count)]
            signed_errors = [forecast[idx] - observed[idx] for idx in range(count)]
            summary = {
                "paired_points": count,
                "mean_abs_error_m3s": round(sum(abs_errors) / count, 3),
                "mean_signed_error_m3s": round(sum(signed_errors) / count, 3),
                "max_abs_error_m3s": round(max(abs_errors), 3),
            }
        return PluginExecutionResult(
            payload={"forecast_error_summary": summary},
            used_config=dict(config),
            metadata={
                "plugin_name": self.plugin_name,
                "plugin_kind": self.plugin_kind,
                "stage": self.stage,
            },
        )


class TankenCaseReportPlugin(ReportPluginBase):
    """Build the final case payload for one Tanken scenario kind."""

    plugin_name = "tanken_case_report"
    stage = PluginStage.REPORT_GENERATION
    summary = "Assemble a structured case report payload from tool and plugin outputs."
    capability_tags = ["reporting", "tanken"]

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        template = str(config.get("template", "")).strip()
        if template not in {"pre_release", "plan_compare", "dynamic_update", "emergency"}:
            raise ValueError("tanken_case_report requires template in {pre_release, plan_compare, dynamic_update, emergency}")
        return {"template": template}

    def validate_inputs(self, context: BasePluginContext) -> None:
        super().validate_inputs(context)
        assert isinstance(context, ReportPluginContext)

    def execute(
        self,
        context: BasePluginContext,
        config: dict[str, Any],
    ) -> PluginExecutionResult:
        self.validate_inputs(context)
        assert isinstance(context, ReportPluginContext)
        normalized = self.validate_config(config)
        template = normalized["template"]
        payload = self._build_payload(template, context.metadata)
        return PluginExecutionResult(
            payload={"report": payload},
            used_config=normalized,
            metadata={
                "plugin_name": self.plugin_name,
                "plugin_kind": self.plugin_kind,
                "stage": self.stage,
            },
        )

    def _build_payload(self, template: str, metadata: dict[str, Any]) -> dict[str, Any]:
        if template == "pre_release":
            scenario = metadata["scenario"]
            stage_context = metadata["stage_context"]
            baseline = metadata["baseline"]
            chain = metadata["chain"]
            trigger_payload = metadata["trigger_payload"]
            alerts = metadata["alerts"]
            return {
                "input_snapshot": metadata["input_snapshot"],
                "data_time_step_hours": scenario["time_step_hours"],
                "rule_context": {
                    "stage": stage_context["stage"],
                    "control_level_m": stage_context["control_level_m"],
                    "release_warning_level_m": stage_context["release_warning_level_m"],
                    "weather_signal": scenario["weather_signal"],
                },
                "decision_summary": {
                    "should_pre_release": bool(trigger_payload.get("should_pre_release", False)),
                    "trigger_reason": metadata["trigger_reason"],
                    "target_control_level_m": stage_context["must_reduce_to_m"],
                    "recommended_start_time": scenario["event_summary"]["start_time"]
                    if trigger_payload.get("should_pre_release", False)
                    else "",
                    "recommended_duration_hours": scenario["duration_hours"]
                    if trigger_payload.get("should_pre_release", False)
                    else 0,
                    "next_step": str(trigger_payload.get("next_step", "Continue monitoring")),
                },
                "candidate_plans": [
                    {
                        "name": "baseline_no_action",
                        "module_type": "constant_release",
                        "declared_outflow_m3s": round(float(scenario["initial_outflow"]), 3),
                        "predicted_max_level_m": baseline["max_level_m"],
                        "predicted_final_level_m": baseline["final_level_m"],
                    },
                    {
                        "name": "recommended_pre_release_plan",
                        "module_type": chain["optimization"]["selected_module_type"],
                        "declared_outflow_m3s": round(float(chain["optimization"]["avg_release_m3s"]), 3),
                        "predicted_max_level_m": chain["simulation"]["max_level_m"],
                        "predicted_final_level_m": chain["simulation"]["final_level_m"],
                        "overall_score": chain["evaluation"]["overall_score"],
                    },
                ],
                "simulation_evidence": {"baseline": baseline, "recommended": chain},
                "alerts": alerts,
                "instruction_delta": {},
                "emergency_action": {},
                "todo_gaps": metadata["todo_gaps"],
            }

        if template == "plan_compare":
            scenario = metadata["scenario"]
            return {
                "input_snapshot": metadata["input_snapshot"],
                "data_time_step_hours": scenario["time_step_hours"],
                "rule_context": {
                    "control_level_m": scenario["stage_context"]["control_level_m"],
                    "downstream_safe_flow_m3s": scenario.get("downstream_limit"),
                    "max_level_m": scenario["constraints"].get("max_level"),
                },
                "decision_summary": {
                    "recommended_plan": metadata["recommended"]["name"],
                    "recommended_outflow_m3s": metadata["recommended"]["declared_outflow_m3s"],
                    "recommended_module_type": metadata["recommended"]["module_type"],
                    "applicability": "Suitable for downstream release-plan comparison demonstrations.",
                    "key_risks": ["Hecheng interval inflow is still estimated heuristically in project scope."],
                    "rejected_plans": metadata["rejected_plans"],
                },
                "candidate_plans": metadata["candidate_plans"],
                "simulation_evidence": {"optimization_chain": metadata["chain"]},
                "alerts": [],
                "instruction_delta": {},
                "emergency_action": {},
                "todo_gaps": metadata["todo_gaps"],
            }

        if template == "dynamic_update":
            scenario = metadata["scenario"]
            stages = metadata["stages"]
            return {
                "input_snapshot": stages[0]["input_snapshot"],
                "data_time_step_hours": stages[0]["input_snapshot"]["time_step_hours"],
                "rule_context": {
                    "update_windows": metadata["stage_windows"],
                    "recompute_trigger": "New observations and an extended forecast window triggered recomputation.",
                    "chosen_flood_event": metadata["chosen_flood_event"],
                    "prediction_column": scenario["prediction_column"],
                },
                "decision_summary": {
                    "version_count": len(stages),
                    "final_stage": stages[-1]["stage"],
                    "final_recommended_outflow_m3s": stages[-1]["selected_plan"]["recommended_outflow_m3s"],
                },
                "candidate_plans": [],
                "simulation_evidence": {"stages": stages},
                "alerts": [],
                "instruction_delta": stages[-1]["instruction_delta"],
                "emergency_action": {},
                "todo_gaps": metadata["todo_gaps"],
            }

        scenario = metadata["scenario"]
        band = metadata["band"]
        candidate = metadata["candidate"]
        return {
            "input_snapshot": metadata["input_snapshot"],
            "data_time_step_hours": scenario["time_step_hours"],
            "rule_context": {"communication_status": "isolated", "rule_band": band["band"]},
            "decision_summary": {
                "current_disposal_level": band["band"],
                "recommended_outflow_cap_m3s": band["max_release_m3s"],
                "generation_paused": band["generation_paused"],
            },
            "candidate_plans": [candidate],
            "simulation_evidence": {"emergency_candidate": candidate},
            "alerts": [
                {
                    "type": "communication_island",
                    "triggered": True,
                    "message": "Local emergency rule mode is active.",
                }
            ],
            "instruction_delta": {},
            "emergency_action": {"action_summary": band["action"]},
            "todo_gaps": metadata["todo_gaps"],
        }
