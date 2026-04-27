"""Shared pytest fixtures for MCP-oriented verification scaffolding."""

from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return repository root from the tests/ directory context."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def dataset_file(tmp_path: Path) -> Path:
    """Create a stable dataset-like input file for contract tests."""
    dataset = tmp_path / "dataset.csv"
    dataset.write_text("timestamp,value\n2026-01-01T00:00:00,1.0\n", encoding="utf-8")
    return dataset


@pytest.fixture
def artifact_dir(tmp_path: Path) -> Path:
    """Create an artifact output root for I/O contract tests."""
    out = tmp_path / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def sample_basin_csv(project_root: Path) -> Path:
    """Return the checked-in basin sample CSV."""
    return project_root / "data" / "basin_001_hourly.csv"
