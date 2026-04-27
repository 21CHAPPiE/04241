from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .utils.config_loader import load_yaml_file


PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_DIR / "configs"
CASES_CONFIG_PATH = CONFIG_DIR / "tanken_cases.yml"
RULES_CONFIG_PATH = CONFIG_DIR / "tanken_rules.yml"
WORKFLOWS_CONFIG_PATH = CONFIG_DIR / "tanken_workflows.yml"


@dataclass(frozen=True)
class TankenCase:
    case_id: str
    section_title: str
    kind: str
    description: str
    default_event: str
    initial_level_m: float
    flood_limit_level_m: float
    season: str
    flood_risk: str
    preferred_modules: tuple[str, ...]
    max_event_points: int
    downstream_limit_m3s: float | None = None
    target_level_m: float | None = None
    max_level_m: float | None = None
    stage_windows: tuple[int, ...] = ()
    prediction_column: str | None = None


def _read_yaml(path: Path) -> dict[str, Any]:
    return load_yaml_file(path)


@lru_cache(maxsize=1)
def load_tanken_cases() -> dict[str, TankenCase]:
    raw = _read_yaml(CASES_CONFIG_PATH).get("cases", {})
    cases: dict[str, TankenCase] = {}
    for case_id, payload in raw.items():
        cases[str(case_id)] = TankenCase(
            case_id=str(case_id),
            section_title=str(payload["section_title"]),
            kind=str(payload["kind"]),
            description=str(payload["description"]),
            default_event=str(payload["default_event"]),
            initial_level_m=float(payload["initial_level_m"]),
            flood_limit_level_m=float(payload["flood_limit_level_m"]),
            season=str(payload["season"]),
            flood_risk=str(payload["flood_risk"]),
            preferred_modules=tuple(str(item) for item in payload.get("preferred_modules", [])),
            max_event_points=int(payload["max_event_points"]),
            downstream_limit_m3s=(
                None if payload.get("downstream_limit_m3s") is None else float(payload["downstream_limit_m3s"])
            ),
            target_level_m=(None if payload.get("target_level_m") is None else float(payload["target_level_m"])),
            max_level_m=(None if payload.get("max_level_m") is None else float(payload["max_level_m"])),
            stage_windows=tuple(int(item) for item in payload.get("stage_windows", [])),
            prediction_column=(
                None if payload.get("prediction_column") in (None, "") else str(payload["prediction_column"])
            ),
        )
    return cases


@lru_cache(maxsize=1)
def load_tanken_rules() -> dict[str, Any]:
    return _read_yaml(RULES_CONFIG_PATH)


@lru_cache(maxsize=1)
def load_tanken_workflows() -> dict[str, Any]:
    return _read_yaml(WORKFLOWS_CONFIG_PATH)


TANKEN_CASES = load_tanken_cases()


def get_tanken_case(case_id: str) -> TankenCase:
    return TANKEN_CASES[case_id]
