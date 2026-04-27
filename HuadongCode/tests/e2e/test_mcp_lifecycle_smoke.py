"""E2E smoke coverage for MCP lifecycle-oriented tool paths."""

from __future__ import annotations

from pathlib import Path

from app.tools import (
    run_calibration_from_paths,
    run_hpo_from_paths,
    run_lifecycle_smoke_from_paths,
    run_training_from_paths,
)


def test_mcp_server_module_exposes_lifecycle_entrypoint(project_root: Path) -> None:
    """Lifecycle smoke should have an executable entrypoint once server module exists."""
    from app import mcp_server

    assert callable(getattr(mcp_server, "main", None)), "Expected callable main() entrypoint"


def test_lifecycle_paths_produce_artifacts(sample_basin_csv: Path, artifact_dir: Path) -> None:
    """Training, calibration, HPO, and smoke aggregator should all produce artifacts."""
    training = run_training_from_paths(dataset_path=str(sample_basin_csv), output_root=str(artifact_dir))
    assert Path(training["artifact_paths"]["model"]).exists()
    assert Path(training["output_manifest_path"]).exists()

    calibration = run_calibration_from_paths(dataset_path=str(sample_basin_csv), output_root=str(artifact_dir))
    assert Path(calibration["artifact_paths"]["calibration"]).exists()

    hpo = run_hpo_from_paths(dataset_path=str(sample_basin_csv), output_root=str(artifact_dir))
    assert Path(hpo["artifact_paths"]["hpo"]).exists()

    smoke = run_lifecycle_smoke_from_paths(dataset_path=str(sample_basin_csv), output_root=str(artifact_dir))
    assert Path(smoke["artifact_paths"]["model"]).exists()
    assert Path(smoke["artifact_paths"]["calibration"]).exists()
    assert Path(smoke["artifact_paths"]["hpo"]).exists()
