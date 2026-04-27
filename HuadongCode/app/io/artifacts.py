"""Artifact write helpers with path-safety checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping


def _resolve_artifact_path(run_dir: str | Path, relative_path: str) -> Path:
    base = Path(run_dir).resolve()
    target = (base / relative_path).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes run directory: {relative_path}") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_json_artifact(run_dir: str | Path, relative_path: str, payload: Mapping[str, Any]) -> Path:
    target = _resolve_artifact_path(run_dir, relative_path)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return target


def write_text_artifact(run_dir: str | Path, relative_path: str, content: str) -> Path:
    target = _resolve_artifact_path(run_dir, relative_path)
    target.write_text(content, encoding="utf-8")
    return target


def write_csv_artifact(run_dir: str | Path, relative_path: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    target = _resolve_artifact_path(run_dir, relative_path)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return target
