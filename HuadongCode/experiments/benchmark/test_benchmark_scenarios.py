from __future__ import annotations

import json
from pathlib import Path

from experiments.benchmark.scenario_631_quick_forecast import run_scenario as run_quick_forecast
from experiments.benchmark.scenario_632_standard_forecast import run_scenario as run_standard_forecast
from experiments.benchmark.scenario_633_complex_flood import run_scenario as run_complex_flood
from experiments.benchmark.scenario_634_rolling_update import run_scenario as run_rolling_update

REQUIRED_REPORT_KEYS = {
    "scenario_id",
    "scenario_title",
    "scene_goal",
    "user_input_examples",
    "task_recognition",
    "workflow_steps",
    "tool_calls",
    "artifacts",
    "result_summary",
    "verification_points",
}


def _load_report(report: dict[str, object]) -> dict[str, object]:
    report_path = Path(str(report["artifacts"]["scenario_report_json"]))
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert REQUIRED_REPORT_KEYS.issubset(loaded.keys())
    return loaded


def test_quick_forecast_benchmark_writes_fastmcp_artifacts(tmp_path: Path) -> None:
    report = run_quick_forecast(output_root=str(tmp_path))
    loaded = _load_report(report)
    assert Path(str(loaded["artifacts"]["forecast_csv"])).exists()
    assert Path(str(loaded["artifacts"]["dataset_profile"])).exists()
    assert Path(str(loaded["artifacts"]["model_assets_profile"])).exists()


def test_standard_forecast_benchmark_writes_analysis_and_forecast(tmp_path: Path) -> None:
    report = run_standard_forecast(output_root=str(tmp_path))
    loaded = _load_report(report)
    assert Path(str(loaded["artifacts"]["analysis_json"])).exists()
    assert Path(str(loaded["artifacts"]["forecast_csv"])).exists()


def test_complex_flood_benchmark_writes_ensemble_and_correction(tmp_path: Path) -> None:
    report = run_complex_flood(output_root=str(tmp_path))
    loaded = _load_report(report)
    assert Path(str(loaded["artifacts"]["ensemble_csv"])).exists()
    assert Path(str(loaded["artifacts"]["corrected_csv"])).exists()
    assert "ensemble_weights" in loaded["result_summary"]


def test_rolling_update_benchmark_writes_comparison(tmp_path: Path) -> None:
    report = run_rolling_update(output_root=str(tmp_path))
    loaded = _load_report(report)
    assert Path(str(loaded["artifacts"]["initial_corrected_csv"])).exists()
    assert Path(str(loaded["artifacts"]["updated_corrected_csv"])).exists()
    assert "initial_vs_updated_peak" in loaded["result_summary"]
