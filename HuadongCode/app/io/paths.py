"""Path resolution and run-directory helpers for runtime orchestration."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_DATA_ROOT = Path("data")
DEFAULT_FILE_ROOT = Path("files")
DEFAULT_RUN_ROOT = DEFAULT_FILE_ROOT / "runs"


def _resolve_existing_file(raw_path: str, fallback_root: Path, label: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = fallback_root / candidate
    resolved = candidate.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"{label} must be a file path: {resolved}")
    return resolved


def resolve_dataset_path(dataset_path: str, data_root: str | Path | None = None) -> Path:
    root = Path(data_root) if data_root is not None else DEFAULT_DATA_ROOT
    return _resolve_existing_file(dataset_path, root, "dataset_path")


def resolve_file_path(file_path: str, file_root: str | Path | None = None) -> Path:
    root = Path(file_root) if file_root is not None else DEFAULT_FILE_ROOT
    return _resolve_existing_file(file_path, root, "file_path")


def create_run_directory(operation: str, run_root: str | Path | None = None, run_id: str | None = None) -> tuple[str, Path]:
    safe_operation = re.sub(r"[^a-z0-9_-]+", "-", operation.lower()).strip("-")
    if not safe_operation:
        raise ValueError("operation must contain at least one alphanumeric character")
    if run_id is None:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    root = Path(run_root) if run_root is not None else DEFAULT_RUN_ROOT
    run_dir = (root / safe_operation / run_id).resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir
