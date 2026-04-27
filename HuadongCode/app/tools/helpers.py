"""Shared path and artifact helpers for tool modules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.io import (
    add_manifest_artifact,
    create_run_directory,
    resolve_dataset_path,
    resolve_file_path,
    write_json_artifact,
    write_text_artifact,
)


def resolve_inputs(dataset_path: str | None, file_path: str | None) -> dict[str, str]:
    if not dataset_path and not file_path:
        raise ValueError("Provide at least one input path: dataset_path or file_path")
    inputs: dict[str, str] = {}
    if dataset_path:
        inputs["dataset_path"] = str(resolve_dataset_path(dataset_path))
    if file_path:
        inputs["file_path"] = str(resolve_file_path(file_path))
    return inputs


def create_run(operation: str, output_root: str | None) -> tuple[str, Path]:
    return create_run_directory(operation=operation, run_root=output_root)


def write_summary_artifacts(
    *,
    run_dir: Path,
    manifest: dict[str, Any],
    summary_text: str,
    payload_name: str,
    payload: Mapping[str, Any],
) -> None:
    from app.tools.common import resolve_small_summary

    summary_path = write_text_artifact(run_dir, "summary.txt", resolve_small_summary(summary_text))
    add_manifest_artifact(manifest, name="summary", path=summary_path, kind="text")
    payload_path = write_json_artifact(run_dir, payload_name, payload)
    add_manifest_artifact(manifest, name=Path(payload_name).stem, path=payload_path, kind="json")


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    import csv

    rows: list[dict[str, Any]] = []
    with Path(path).expanduser().resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    return rows


def read_numeric_column(path: str | Path, column: str) -> list[float]:
    rows = read_csv_rows(path)
    values: list[float] = []
    for row in rows:
        raw = row.get(column)
        if raw is None or raw == "":
            continue
        values.append(float(raw))
    return values


def read_text_column(path: str | Path, column: str) -> list[str]:
    rows = read_csv_rows(path)
    values: list[str] = []
    for row in rows:
        raw = row.get(column)
        if raw is None or raw == "":
            continue
        values.append(str(raw))
    return values


def detect_time_column(path: str | Path) -> str | None:
    rows = read_csv_rows(path)
    if not rows:
        return None
    for candidate in ("timestamp", "time", "Time"):
        if candidate in rows[0]:
            return candidate
    return None
