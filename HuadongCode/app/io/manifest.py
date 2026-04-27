"""Manifest helpers for deterministic run metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from app.io.artifacts import write_json_artifact


def create_manifest(
    *,
    operation: str,
    run_id: str,
    run_dir: str | Path,
    inputs: Mapping[str, str],
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "run_id": run_id,
        "run_dir": str(Path(run_dir).resolve()),
        "started_at": datetime.now(tz=UTC).isoformat(),
        "inputs": dict(inputs),
        "options": dict(options or {}),
        "artifacts": [],
        "summary": "",
    }


def add_manifest_artifact(manifest: dict[str, Any], *, name: str, path: str | Path, kind: str) -> None:
    artifact_path = Path(path).resolve()
    size_bytes = artifact_path.stat().st_size if artifact_path.exists() else 0
    manifest["artifacts"].append(
        {
            "name": name,
            "kind": kind,
            "path": str(artifact_path),
            "size_bytes": size_bytes,
        }
    )


def finalize_manifest(manifest: dict[str, Any], *, status: str, summary: str) -> dict[str, Any]:
    manifest["status"] = status
    manifest["completed_at"] = datetime.now(tz=UTC).isoformat()
    manifest["summary"] = " ".join(summary.split())[:240]
    return manifest


def write_manifest(run_dir: str | Path, manifest: Mapping[str, Any]) -> Path:
    return write_json_artifact(run_dir, "manifest.json", manifest)
