"""Integration coverage for the MCP vertical slice."""

from __future__ import annotations

from pathlib import Path

from app.tools import (
    run_correction_from_paths,
    run_ensemble_from_paths,
    run_forecast_from_paths,
    run_risk_from_paths,
    run_warning_from_paths,
)


def test_mcp_server_module_exposes_bootstrap_callable(project_root: Path) -> None:
    """Vertical slice should expose a server bootstrap callable when mcp_server lands."""
    from app import mcp_server

    assert callable(getattr(mcp_server, "main", None))
    assert hasattr(mcp_server, "mcp")


def test_vertical_slice_runs_forecast_to_warning_chain(
    sample_basin_csv: Path,
    artifact_dir: Path,
) -> None:
    """Representative chain should write artifacts for forecast -> ensemble -> correction -> risk -> warning."""
    forecast = run_forecast_from_paths(dataset_path=str(sample_basin_csv), output_root=str(artifact_dir))
    forecast_csv = Path(forecast["artifact_paths"]["forecast"])
    assert forecast_csv.exists()
    assert Path(forecast["output_manifest_path"]).exists()

    ensemble = run_ensemble_from_paths(file_path=str(forecast_csv), output_root=str(artifact_dir))
    ensemble_csv = Path(ensemble["artifact_paths"]["ensemble"])
    assert ensemble_csv.exists()

    correction = run_correction_from_paths(
        file_path=str(ensemble_csv),
        output_root=str(artifact_dir),
        options={"observation_dataset": str(sample_basin_csv), "observation_column": "streamflow"},
    )
    corrected_csv = Path(correction["artifact_paths"]["correction"])
    assert corrected_csv.exists()

    risk = run_risk_from_paths(file_path=str(corrected_csv), output_root=str(artifact_dir))
    risk_json = Path(risk["artifact_paths"]["risk"])
    assert risk_json.exists()

    warning = run_warning_from_paths(file_path=str(corrected_csv), output_root=str(artifact_dir))
    warning_json = Path(warning["artifact_paths"]["warning"])
    assert warning_json.exists()
    assert warning["status"] == "completed"
