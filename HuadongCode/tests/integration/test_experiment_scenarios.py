from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.scenario_631_quick_forecast import run_scenario as run_quick_forecast
from experiments.scenario_632_standard_forecast import run_scenario as run_standard_forecast
from experiments.scenario_633_complex_flood import run_scenario as run_complex_flood
from experiments.scenario_634_rolling_update import run_scenario as run_rolling_update

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
    assert report_path.exists()
    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert REQUIRED_REPORT_KEYS.issubset(loaded.keys())
    return loaded


def test_quick_forecast_scenario_writes_forecast_and_report(tmp_path: Path) -> None:
    report = run_quick_forecast(output_root=str(tmp_path))
    loaded = _load_report(report)

    forecast_csv = Path(str(loaded["artifacts"]["forecast_csv"]))
    assert forecast_csv.exists()
    assert loaded["scenario_id"] == "6.3.1"


def test_standard_forecast_scenario_writes_analysis_and_forecast(tmp_path: Path) -> None:
    report = run_standard_forecast(output_root=str(tmp_path))
    loaded = _load_report(report)

    analysis_json = Path(str(loaded["artifacts"]["analysis_json"]))
    forecast_csv = Path(str(loaded["artifacts"]["forecast_csv"]))
    assert analysis_json.exists()
    assert forecast_csv.exists()
    assert "trend_analysis" in loaded["result_summary"]


def test_complex_flood_scenario_writes_ensemble_and_correction(tmp_path: Path) -> None:
    report = run_complex_flood(output_root=str(tmp_path))
    loaded = _load_report(report)

    ensemble_csv = Path(str(loaded["artifacts"]["ensemble_csv"]))
    corrected_csv = Path(str(loaded["artifacts"]["corrected_csv"]))
    assert ensemble_csv.exists()
    assert corrected_csv.exists()
    assert "screening" in loaded["result_summary"]
    assert "error_metrics" in loaded["result_summary"]
    assert "2016/" in str(loaded["result_summary"]["corrected_peak"]["peak_position"])

    with ensemble_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert "timestamp" in reader.fieldnames

    with corrected_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert "timestamp" in reader.fieldnames


def test_rolling_update_scenario_writes_initial_and_updated_comparison(tmp_path: Path) -> None:
    report = run_rolling_update(output_root=str(tmp_path))
    loaded = _load_report(report)

    initial_csv = Path(str(loaded["artifacts"]["initial_corrected_csv"]))
    updated_csv = Path(str(loaded["artifacts"]["updated_corrected_csv"]))
    assert initial_csv.exists()
    assert updated_csv.exists()
    assert "initial_vs_updated_peak" in loaded["result_summary"]
    assert loaded["result_summary"]["delta_summary"]
    assert "2016/" in str(loaded["result_summary"]["initial_vs_updated_peak"]["initial"]["peak_position"])
    assert "2016/" in str(loaded["result_summary"]["initial_vs_updated_peak"]["updated"]["peak_position"])
