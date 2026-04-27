from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from pyresops.domain.policy import ExecutionContext
from pyresops.domain.rule import DispatchRule, RuleAction, RuleSet
from pyresops.rules import RuleFactory, RuleRegistry, register_builtin_rules

from .tanken_config import load_tanken_rules


def _build_dispatch_rule(rule_payload: dict[str, Any]) -> DispatchRule:
    return DispatchRule(
        id=str(rule_payload["id"]),
        name=str(rule_payload.get("name", rule_payload["id"])),
        condition=dict(rule_payload.get("condition", {})),
        actions=[RuleAction(**item) for item in rule_payload.get("actions", [])],
        priority=int(rule_payload.get("priority", 100)),
        enabled=bool(rule_payload.get("enabled", True)),
        stop_on_match=bool(rule_payload.get("stop_on_match", False)),
        metadata=dict(rule_payload.get("metadata", {})),
    )


@lru_cache(maxsize=1)
def _build_registry() -> RuleRegistry:
    registry = RuleRegistry()
    register_builtin_rules(registry)
    return registry


@lru_cache(maxsize=1)
def _build_factory() -> RuleFactory:
    return RuleFactory(_build_registry())


@lru_cache(maxsize=None)
def _load_rule_set(rule_family: str, subgroup: str | None = None) -> RuleSet:
    family = load_tanken_rules()[rule_family]
    if subgroup is not None:
        if not isinstance(family, dict):
            raise TypeError(f"Rule family {rule_family} does not contain subgroups")
        family = family[subgroup]
    elif isinstance(family, dict):
        raise TypeError(f"Rule family {rule_family} is nested and must be accessed by subgroup")
    return RuleSet(rules=[_build_dispatch_rule(item) for item in family])


def _evaluate_rule_set(rule_set: RuleSet, context: ExecutionContext) -> dict[str, Any] | None:
    factory = _build_factory()
    for rule in rule_set.enabled_rules():
        evaluator = factory.create(rule)
        if evaluator is None:
            continue
        if evaluator.match(context):
            for action in evaluator.produce_actions(context):
                if action.action_type == "emit_event":
                    return dict(action.parameters)
            return {}
    return None


def _resolve_rule_payload(
    *,
    rule_family: str,
    context: ExecutionContext,
    subgroup: str | None = None,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _evaluate_rule_set(_load_rule_set(rule_family, subgroup), context)
    if payload is None:
        return dict(default or {})
    return payload


def resolve_stage_context(start_time: datetime, weather_signal: dict[str, Any]) -> dict[str, Any]:
    context = ExecutionContext(
        step_index=0,
        state={},
        inflow=0.0,
        proposed_outflow=0.0,
        directives={
            "month": start_time.month,
            "day": start_time.day,
            "severe_weather": bool(weather_signal.get("severe_weather", False)),
        },
    )
    return _resolve_rule_payload(rule_family="stage_rules", context=context)


def resolve_pre_release_decision(
    *,
    current_level_m: float,
    predicted_max_level_m: float,
    stage_context: dict[str, Any],
    weather_signal: dict[str, Any],
) -> dict[str, Any]:
    context = ExecutionContext(
        step_index=0,
        state={"current_level_m": float(current_level_m)},
        inflow=0.0,
        proposed_outflow=0.0,
        forecast={"predicted_max_level_m": float(predicted_max_level_m)},
        directives={
            "stage": stage_context.get("stage"),
            "control_level_m": float(stage_context.get("control_level_m", 0.0)),
            "severe_weather": bool(weather_signal.get("severe_weather", False)),
        },
    )
    return _resolve_rule_payload(rule_family="pre_release_rules", context=context)


def resolve_alert_payload(
    alert_type: str,
    *,
    current_level_m: float,
    predicted_max_level_m: float,
    stage_context: dict[str, Any],
    should_pre_release: bool,
) -> dict[str, Any]:
    context = ExecutionContext(
        step_index=0,
        state={"current_level_m": float(current_level_m)},
        inflow=0.0,
        proposed_outflow=0.0,
        forecast={"predicted_max_level_m": float(predicted_max_level_m)},
        directives={
            "release_warning_level_m": float(stage_context.get("release_warning_level_m", 0.0)),
            "should_pre_release": bool(should_pre_release),
        },
    )
    return _resolve_rule_payload(
        rule_family="alert_rules",
        subgroup=alert_type,
        context=context,
        default={"type": alert_type, "triggered": False},
    )


def resolve_emergency_band(level_m: float) -> dict[str, Any]:
    context = ExecutionContext(
        step_index=0,
        state={"current_level_m": float(level_m)},
        inflow=0.0,
        proposed_outflow=0.0,
    )
    return _resolve_rule_payload(rule_family="emergency_band_rules", context=context)


def load_plan_compare_templates() -> dict[str, dict[str, Any]]:
    return dict(load_tanken_rules()["plan_compare_templates"])


def load_global_defaults() -> dict[str, Any]:
    return dict(load_tanken_rules().get("global_defaults", {}))
