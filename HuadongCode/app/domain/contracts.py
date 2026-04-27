"""Domain contracts for MCP tool responses."""

from __future__ import annotations

from typing import TypedDict


class ToolExecutionResult(TypedDict):
    status: str
    operation: str
    run_id: str
    run_dir: str
    output_manifest_path: str
    artifact_paths: dict[str, str]
    small_summary: str
