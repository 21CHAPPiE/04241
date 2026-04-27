from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Any, Callable

from pyresops.domain.constraint import Constraint, ConstraintSet
from pyresops.domain.forecast import ForecastBundle, ForecastSeries
from pyresops.domain.program import DispatchProgram, ModuleInstance, TimeHorizon
from pyresops.domain.reservoir import ReservoirState
from pyresops.plugins import PluginManager
from pyresops.providers import DataRequest, ProviderManager, ProviderRegistry, ReservoirBootstrap, register_builtin_providers
from pyresops.services import EvaluationService, OptimizationService, ProgramService, SimulationService, SnapshotService

from .tanken_config import load_tanken_workflows


@lru_cache(maxsize=1)
def build_project_plugin_manager() -> PluginManager:
    manager = PluginManager()
    workflow_config = load_tanken_workflows()
    for import_path in workflow_config.get("plugin_imports", []):
        manager.loader.load_from_path(str(import_path))
    return manager


@lru_cache(maxsize=1)
def build_project_provider_manager() -> ProviderManager:
    registry = ProviderRegistry()
    register_builtin_providers(registry)
    return ProviderManager(registry)


@lru_cache(maxsize=1)
def load_case_workflows() -> dict[str, Any]:
    return dict(load_tanken_workflows().get("workflows", {}))


def get_case_workflow(case_id: str) -> dict[str, Any]:
    workflows = load_case_workflows()
    if case_id not in workflows:
        raise KeyError(f"Workflow config not found for case {case_id}")
    return dict(workflows[case_id])


def load_project_bootstrap(locator: str) -> ReservoirBootstrap:
    manager = build_project_provider_manager()
    result = manager.ensure(
        DataRequest(
            target_type="reservoir_bootstrap",
            source_hint="yaml",
            locator=locator,
        )
    )
    assert isinstance(result, ReservoirBootstrap)
    return result


@dataclass
class ProjectToolRuntime:
    scenario: dict[str, Any]
    bootstrap: ReservoirBootstrap
    plugin_manager: PluginManager

    def __post_init__(self) -> None:
        self.spec = self.scenario["reservoir_spec"]
        self.snapshot_service = SnapshotService()
        self.program_service = ProgramService()
        self.simulation_service = SimulationService(
            self.spec,
            self.program_service.get_module_registry(),
            plugin_manager=self.plugin_manager,
        )
        self.evaluation_service = EvaluationService(self.spec)
        self.optimization_service = OptimizationService(
            self.spec,
            self.program_service,
            plugin_manager=self.plugin_manager,
        )
        self.initial_state = self._build_initial_state()
        self.snapshot_service.update_snapshot(self.spec.id, self.initial_state)

    def make_tools(self) -> dict[str, Callable[..., dict[str, Any]]]:
        return {
            "get_reservoir_status": self.get_reservoir_status,
            "query_dispatch_rules": self.query_dispatch_rules,
            "optimize_release_plan": self.optimize_release_plan,
            "simulate_dispatch_program": self.simulate_dispatch_program,
            "evaluate_dispatch_result": self.evaluate_dispatch_result,
        }

    def get_reservoir_status(self, scenario_id: str) -> dict[str, Any]:
        self._require_scenario(scenario_id)
        inflow_sequence = list(self.scenario.get("benchmark_inflow_series_m3s", []))
        sequence_summary = (
            {
                "step_count": len(inflow_sequence),
                "first_inflow_m3s": inflow_sequence[0],
                "max_inflow_m3s": max(inflow_sequence),
                "min_inflow_m3s": min(inflow_sequence),
            }
            if inflow_sequence
            else None
        )
        return {
            "scenario_id": scenario_id,
            "current_level_m": self.scenario["current_level"],
            "initial_storage_billion_m3": self.scenario["initial_storage"],
            "current_inflow_m3s": self.scenario["initial_inflow"],
            "forecast_inflow_m3s": self.scenario["inflow"],
            "dead_level_m": self.spec.dead_level,
            "normal_level_m": self.spec.normal_level,
            "flood_limit_level_m": self.scenario["flood_limit_level"],
            "design_flood_level_m": self.spec.design_flood_level,
            "total_capacity_billion_m3": self.spec.total_capacity,
            "flood_capacity_billion_m3": self.spec.flood_capacity,
            "season": self.scenario["season"],
            "flood_risk": self.scenario["flood_risk"],
            "benchmark_preferred_modules": self.scenario.get("benchmark_preferred_modules", []),
            "forecast_sequence_summary": sequence_summary,
            "carry_over_plan": self.scenario.get("carry_over_plan"),
        }

    def query_dispatch_rules(self, scenario_id: str) -> dict[str, Any]:
        self._require_scenario(scenario_id)
        constraints = dict(self.scenario.get("constraints", {}))
        task_constraints = dict(self.scenario.get("task_constraints", {}))
        return {
            "scenario_id": scenario_id,
            "name": self.scenario["name"],
            "description": self.scenario["description"],
            "hard_constraints": {
                "flood_limit_level_m": self.scenario["flood_limit_level"],
                "dead_level_m": self.spec.dead_level,
                "normal_level_m": self.spec.normal_level,
                "max_level_m": constraints.get("max_level"),
                "design_flood_level_m": self.spec.design_flood_level,
                "ecological_min_flow_m3s": constraints.get("ecological_min_flow", 50.0),
                "downstream_limit_m3s": self.scenario.get("downstream_limit"),
            },
            "objectives": dict(self.scenario.get("objectives", {})),
            "task_constraints": task_constraints,
            "flood_limit_level_m": self.scenario["flood_limit_level"],
            "eco_min_flow_m3s": constraints.get("ecological_min_flow", 50.0),
            "downstream_safe_flow_m3s": self.scenario.get("downstream_limit"),
            "deadline_hours": float(self.scenario["duration_hours"]),
            "target_level_m": self.scenario.get("target_level"),
            "window_hours": float(self.scenario["duration_hours"]),
            "benchmark_preferred_modules": self.scenario.get("benchmark_preferred_modules", []),
            "benchmark_source_markdown": self.scenario.get("benchmark_source_markdown"),
            "requested_module_type": self.scenario.get("requested_module_type"),
            "carry_over_plan": self.scenario.get("carry_over_plan"),
        }

    def optimize_release_plan(
        self,
        scenario_id: str,
        horizon_hours: int = 0,
        requested_module_type: str = "",
        min_flow: float = 50.0,
        max_flow: float = 0.0,
        control_interval_seconds: int = 0,
    ) -> dict[str, Any]:
        self._require_scenario(scenario_id)
        forecast = self._build_forecast(horizon_hours_override=horizon_hours or None)
        constraints = dict(self.scenario.get("constraints", {}))
        constraints["ecological_min_flow"] = float(min_flow)
        if max_flow > 0:
            constraints["max_release"] = float(max_flow)
        result = self.optimization_service.optimize_release_plan(
            initial_state=self.initial_state.copy_with_update(),
            forecast=forecast,
            constraints=constraints,
            objectives=dict(self.scenario.get("objectives", {})),
            task_constraints=dict(self.scenario.get("task_constraints", {})),
            directives={"season": self.scenario["season"], "flood_risk": self.scenario["flood_risk"]},
            allowed_module_types=list(self.scenario.get("benchmark_preferred_modules", [])) or None,
            requested_module_type=requested_module_type or None,
            name=f"{self.scenario['id']}_optimized",
            metadata={"scenario_id": self.scenario["id"]},
        )
        selected = result.selected_candidate
        return {
            "scenario_id": scenario_id,
            "program_id": result.program.id,
            "selected_module_type": selected.module_type,
            "selected_module_parameters": dict(selected.module_parameters),
            "feasible_solution_found": selected.feasible,
            "fallback_applied": result.fallback_applied,
            "requested_module_type": result.requested_module_type,
            "horizon_hours": horizon_hours or None,
            "control_interval_seconds": control_interval_seconds or None,
            "final_level_m": round(float(selected.simulation_result.snapshots[-1].level), 3),
            "avg_release_m3s": round(float(selected.simulation_result.avg_outflow), 3),
            "avg_outflow_m3s": round(float(selected.simulation_result.avg_outflow), 3),
            "release_values_m3s": [round(float(snap.outflow), 3) for snap in selected.simulation_result.snapshots],
            "min_release_m3s": round(min(float(snap.outflow) for snap in selected.simulation_result.snapshots), 3),
            "max_release_m3s": round(max(float(snap.outflow) for snap in selected.simulation_result.snapshots), 3),
            "family_attempts": list(result.family_attempts),
        }

    def simulate_dispatch_program(
        self,
        scenario_id: str,
        target_outflow: float,
        module_type: str = "constant_release",
        module_parameters_json: str = "",
    ) -> dict[str, Any]:
        self._require_scenario(scenario_id)
        program = self._build_program(
            scenario_id=scenario_id,
            module_type=module_type,
            target_outflow=target_outflow,
            module_parameters_json=module_parameters_json,
            purpose="sim",
        )
        forecast = self._build_forecast()
        result = self.simulation_service.run_simulation(
            program,
            self.initial_state.copy_with_update(),
            forecast,
        )
        return {
            "scenario_id": scenario_id,
            "declared_outflow": target_outflow,
            "target_outflow": target_outflow,
            "module_type": module_type,
            "module_parameters": self._resolve_module_parameters(module_type, target_outflow, module_parameters_json),
            "max_level_m": round(result.max_level, 3),
            "min_level_m": round(result.min_level, 3),
            "final_level_m": round(result.snapshots[-1].level, 3),
            "avg_outflow_m3s": round(result.avg_outflow, 1),
            "total_steps": len(result.snapshots),
            "snapshots_sample": self._sample_snapshots(result),
        }

    def evaluate_dispatch_result(
        self,
        scenario_id: str,
        target_outflow: float,
        eco_min_flow: float = 50.0,
        module_type: str = "constant_release",
        module_parameters_json: str = "",
    ) -> dict[str, Any]:
        self._require_scenario(scenario_id)
        program = self._build_program(
            scenario_id=scenario_id,
            module_type=module_type,
            target_outflow=target_outflow,
            module_parameters_json=module_parameters_json,
            purpose="eval",
        )
        forecast = self._build_forecast()
        result = self.simulation_service.run_simulation(
            program,
            self.initial_state.copy_with_update(),
            forecast,
        )
        constraint_set = self._build_constraint_set(eco_min_flow=eco_min_flow)
        evaluation = self.evaluation_service.evaluate(result, constraint_set=constraint_set)
        return {
            "scenario_id": scenario_id,
            "declared_outflow": target_outflow,
            "target_outflow": target_outflow,
            "module_type": module_type,
            "module_parameters": self._resolve_module_parameters(module_type, target_outflow, module_parameters_json),
            "final_level_m": round(result.snapshots[-1].level, 3),
            "target_level_m": self.scenario.get("target_level"),
            "overall_score": round(evaluation.overall_score, 4),
            "flood_control_score": round(evaluation.flood_control_score, 4),
            "water_supply_score": round(evaluation.water_supply_score, 4),
            "power_generation_score": round(evaluation.power_generation_score, 4),
            "ecological_score": round(evaluation.ecological_score, 4),
            "constraint_violations_count": len(evaluation.constraint_violations),
            "constraint_violations": list(evaluation.constraint_violations),
        }

    def _require_scenario(self, scenario_id: str) -> None:
        if scenario_id != self.scenario["id"]:
            raise ValueError(f"Unknown scenario_id: {scenario_id}")

    def _build_initial_state(self) -> ReservoirState:
        return ReservoirState(
            timestamp=self.scenario["benchmark_start_time"],
            level=float(self.scenario["current_level"]),
            storage=float(self.scenario["initial_storage"]),
            inflow=float(self.scenario["initial_inflow"]),
            outflow=float(self.scenario["initial_outflow"]),
            metadata={"reservoir_id": self.spec.id},
        )

    def _build_forecast(self, *, horizon_hours_override: int | None = None) -> ForecastBundle:
        step_hours = int(self.scenario["time_step_hours"])
        values = list(self.scenario["benchmark_inflow_series_m3s"])
        if horizon_hours_override is not None:
            max_steps = max(1, int(round(horizon_hours_override / step_hours)))
            values = values[:max_steps]
        timestamps = [
            self.scenario["benchmark_start_time"] + timedelta(hours=step_hours * idx)
            for idx in range(len(values))
        ]
        return ForecastBundle(
            forecast_time=self.scenario["benchmark_start_time"],
            series=[
                ForecastSeries(
                    variable="inflow",
                    timestamps=timestamps,
                    values=[float(value) for value in values],
                    unit="m3/s",
                )
            ],
        )

    def _build_program(
        self,
        *,
        scenario_id: str,
        module_type: str,
        target_outflow: float,
        module_parameters_json: str,
        purpose: str,
    ) -> DispatchProgram:
        parameters = self._resolve_module_parameters(module_type, target_outflow, module_parameters_json)
        horizon = TimeHorizon(
            start=self.scenario["benchmark_start_time"],
            end=self.scenario["benchmark_start_time"] + timedelta(hours=self.scenario["duration_hours"]),
            time_step=int(self.scenario["time_step_hours"] * 3600),
        )
        return DispatchProgram(
            id=f"{scenario_id}_{purpose}",
            name=f"{self.scenario['name']}_{purpose}",
            time_horizon=horizon,
            module_sequence=[ModuleInstance(module_type=module_type, parameters=parameters)],
        )

    def _resolve_module_parameters(
        self,
        module_type: str,
        target_outflow: float,
        module_parameters_json: str,
    ) -> dict[str, Any]:
        if module_parameters_json:
            return json.loads(module_parameters_json)
        return {"target_release": float(target_outflow)}

    def _build_constraint_set(self, *, eco_min_flow: float) -> ConstraintSet:
        constraints = [
            Constraint(
                id="eco_flow",
                name="Ecological minimum flow",
                constraint_type="ecological_min_flow",
                parameters={"min_flow": float(eco_min_flow)},
                priority=9,
            )
        ]
        max_level = self.scenario["constraints"].get("max_level")
        if max_level is not None:
            constraints.append(
                Constraint(
                    id="level_max",
                    name="Maximum level",
                    constraint_type="level_max",
                    parameters={"max_level": float(max_level)},
                    priority=10,
                )
            )
        return ConstraintSet(constraints=constraints)

    @staticmethod
    def _sample_snapshots(result) -> list[dict[str, Any]]:
        step = max(1, len(result.snapshots) // 10)
        return [
            {
                "step": idx,
                "timestamp": snap.timestamp.isoformat(),
                "level_m": round(snap.level, 3),
                "inflow_m3s": round(snap.inflow, 1),
                "outflow_m3s": round(snap.outflow, 1),
            }
            for idx, snap in enumerate(result.snapshots[::step])
        ]


def build_project_tool_runtime(scenario: dict[str, Any]) -> ProjectToolRuntime:
    bootstrap = load_project_bootstrap(str(scenario["resolved_reservoir_config_path"]))
    return ProjectToolRuntime(
        scenario=scenario,
        bootstrap=bootstrap,
        plugin_manager=build_project_plugin_manager(),
    )
