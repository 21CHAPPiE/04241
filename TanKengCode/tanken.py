from __future__ import annotations

from pathlib import Path
from typing import Any

from .scenario_executor import execute_all_cases, execute_case
from .tanken_common import DEFAULT_RESERVOIR_CONFIG, build_tanken_runtime_scenario
from .tanken_config import TANKEN_CASES


def run_tanken_demo(
    *,
    case_id: str,
    event_csv_path: str | Path | None = None,
    reservoir_config_path: str | Path = DEFAULT_RESERVOIR_CONFIG,
    save_result: bool = True,
) -> dict[str, Any]:
    return execute_case(
        case_id=case_id,
        event_csv_path=event_csv_path,
        reservoir_config_path=reservoir_config_path,
        save_result=save_result,
    )


def run_all_tanken_cases(
    *,
    reservoir_config_path: str | Path = DEFAULT_RESERVOIR_CONFIG,
    save_result: bool = True,
) -> dict[str, dict[str, Any]]:
    return execute_all_cases(
        reservoir_config_path=reservoir_config_path,
        save_result=save_result,
    )


__all__ = [
    "DEFAULT_RESERVOIR_CONFIG",
    "TANKEN_CASES",
    "build_tanken_runtime_scenario",
    "run_all_tanken_cases",
    "run_tanken_demo",
]
