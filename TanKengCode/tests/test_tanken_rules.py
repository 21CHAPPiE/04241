from __future__ import annotations

from datetime import datetime

from project.tanken_config import TANKEN_CASES, load_tanken_rules
from project.tanken_rules_bridge import (
    resolve_alert_payload,
    resolve_emergency_band,
    resolve_pre_release_decision,
    resolve_stage_context,
)
from pyresops.domain import DispatchRule, ExecutionContext
from pyresops.rules import ContextRuleOp, RuleFactory, RuleRegistry, register_builtin_rules


def test_tanken_cases_loaded_from_yaml() -> None:
    case = TANKEN_CASES["6.4.3"]
    assert case.default_event == "2024072617_with_pred.csv"
    assert case.stage_windows == (8, 16, 24)
    assert case.prediction_column == "predict"


def test_tanken_rules_yaml_contains_expected_families() -> None:
    payload = load_tanken_rules()
    assert "stage_rules" in payload
    assert "pre_release_rules" in payload
    assert "emergency_band_rules" in payload
    assert "plan_compare_templates" in payload


def test_builtin_rules_register_context_expression_evaluator() -> None:
    registry = RuleRegistry()
    register_builtin_rules(registry)
    assert "context_expression" in registry.list_types()

    factory = RuleFactory(registry)
    rule = DispatchRule(
        id="r1",
        name="simple",
        metadata={"rule_type": "context_expression"},
        condition={"left": "state.level", "op": ContextRuleOp.GTE.value, "right_value": 156.5},
    )
    evaluator = factory.create(rule)
    assert evaluator is not None
    assert evaluator.match(
        ExecutionContext(step_index=0, state={"level": 156.6}, inflow=0.0, proposed_outflow=0.0)
    )


def test_context_rule_op_enum_has_expected_members() -> None:
    assert ContextRuleOp.ALWAYS.value == "always"
    assert ContextRuleOp.ALL.value == "all"
    assert ContextRuleOp.GTE.value == "gte"


def test_resolve_stage_context_uses_yaml_rules() -> None:
    stage = resolve_stage_context(
        datetime(2024, 7, 10, 8, 0, 0),
        {"severe_weather": True},
    )
    assert stage["stage"] == "transition"
    assert stage["control_level_m"] == 156.5


def test_resolve_pre_release_decision_uses_rule_bridge() -> None:
    decision = resolve_pre_release_decision(
        current_level_m=156.8,
        predicted_max_level_m=157.2,
        stage_context={"stage": "typhoon", "control_level_m": 156.5},
        weather_signal={"severe_weather": False},
    )
    assert decision["should_pre_release"] is True
    assert decision["trigger_reason"] == "predicted_max_exceeds_control_level"


def test_resolve_alert_payload_release_warning_uses_dynamic_threshold() -> None:
    payload = resolve_alert_payload(
        "release_warning",
        current_level_m=156.1,
        predicted_max_level_m=156.2,
        stage_context={"release_warning_level_m": 156.0},
        should_pre_release=True,
    )
    assert payload["triggered"] is True
    assert payload["type"] == "flood_release_warning"


def test_resolve_emergency_band_uses_yaml_rule_band_mapping() -> None:
    band = resolve_emergency_band(162.9)
    assert band["band"] == "162.84m-163.54m"
    assert band["max_release_m3s"] == 9270.0
