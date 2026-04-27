from __future__ import annotations

from typing import Any

from pyresops.plugins import PluginExecutionResult, PluginStage, PostPluginBase
from pyresops.plugins.models import BasePluginContext, PostPluginContext

from project.utils.muskingum import MuskingumParams, check_downstream_safety, compute_hecheng_flow


class HechengDownstreamSafetyPlugin(PostPluginBase):
    """Route discharge and evaluate downstream safety for the Tanken scenarios."""

    plugin_name = "tanken_hecheng_downstream"
    stage = PluginStage.POST_SIMULATION
    summary = "Route outflow with Muskingum plus interval inflow and assess downstream safety."
    capability_tags = ["routing", "downstream_safety", "tanken"]
    required_inputs = ["simulation_result.snapshots[outflow]", "config.interval_flow_series"]
    optional_inputs = ["config.safe_flow", "config.k", "config.x", "config.dt_hours", "config.initial_flow"]
    output_schema = {
        "type": "object",
        "properties": {
            "downstream_safety": {"type": "object"},
            "hecheng_total": {"type": "array"},
            "tankan_routed": {"type": "array"},
            "interval_flow": {"type": "array"},
        },
    }

    def validate_config(self, config: dict[str, Any]) -> dict[str, Any]:
        interval = config.get("interval_flow_series")
        if not isinstance(interval, list):
            raise ValueError("tanken_hecheng_downstream requires 'interval_flow_series'")
        normalized = {
            "interval_flow_series": [float(value) for value in interval],
            "safe_flow": float(config.get("safe_flow", 14000.0)),
            "k": float(config.get("k", 5.0)),
            "x": float(config.get("x", 0.25)),
            "dt_hours": float(config.get("dt_hours", 1.0)),
            "initial_flow": None if config.get("initial_flow") is None else float(config["initial_flow"]),
        }
        MuskingumParams(K=normalized["k"], x=normalized["x"], dt=normalized["dt_hours"]).validate()
        return normalized

    def validate_inputs(self, context: BasePluginContext) -> None:
        super().validate_inputs(context)
        assert isinstance(context, PostPluginContext)
        if not context.simulation_result or not context.simulation_result.snapshots:
            raise ValueError("tanken_hecheng_downstream requires simulation snapshots")

    def execute(
        self,
        context: BasePluginContext,
        config: dict[str, Any],
    ) -> PluginExecutionResult:
        self.validate_inputs(context)
        assert isinstance(context, PostPluginContext)
        normalized = self.validate_config(config)
        outflow_series = [float(snapshot.outflow) for snapshot in context.simulation_result.snapshots]
        routed = compute_hecheng_flow(
            outflow_series,
            interval_flow_series=normalized["interval_flow_series"],
            muskingum_params=MuskingumParams(
                K=normalized["k"],
                x=normalized["x"],
                dt=normalized["dt_hours"],
            ),
            initial_flow=normalized["initial_flow"],
        )
        safety = check_downstream_safety(
            routed["hecheng_total"],
            safe_flow=normalized["safe_flow"],
        )
        return PluginExecutionResult(
            payload={
                "tankan_routed": routed["tankan_routed"],
                "interval_flow": routed["interval_flow"],
                "hecheng_total": routed["hecheng_total"],
                "downstream_safety": safety,
            },
            diagnostics={
                "step_count": len(outflow_series),
                "max_outflow_m3s": max(outflow_series) if outflow_series else 0.0,
                "max_hecheng_flow_m3s": max(routed["hecheng_total"]) if routed["hecheng_total"] else 0.0,
            },
            used_config=normalized,
            metadata={
                "plugin_name": self.plugin_name,
                "plugin_kind": self.plugin_kind,
                "stage": self.stage,
            },
        )
