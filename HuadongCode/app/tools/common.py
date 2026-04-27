"""Shared tool-layer helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.domain import ToolExecutionResult
from app.io import finalize_manifest, write_manifest


def resolve_small_summary(summary: str) -> str:
    return " ".join(summary.split())[:240]


def artifact_response(
    *,
    operation: str,
    run_id: str,
    run_dir: Path,
    manifest_path: Path,
    summary: str,
    artifacts: dict[str, str],
) -> ToolExecutionResult:
    return {
        "status": "completed",
        "operation": operation,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "output_manifest_path": str(manifest_path),
        "artifact_paths": artifacts,
        "small_summary": resolve_small_summary(summary),
    }


def finalize_and_respond(
    *,
    manifest: dict[str, Any],
    run_dir: Path,
    run_id: str,
    operation: str,
    summary: str,
) -> ToolExecutionResult:
    finalize_manifest(manifest, status="completed", summary=summary)
    manifest_path = write_manifest(run_dir, manifest)
    artifacts = {entry["name"]: entry["path"] for entry in manifest["artifacts"]}
    artifacts["manifest"] = str(manifest_path)
    return artifact_response(
        operation=operation,
        run_id=run_id,
        run_dir=run_dir,
        manifest_path=manifest_path,
        summary=summary,
        artifacts=artifacts,
    )
