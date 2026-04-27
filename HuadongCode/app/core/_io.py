"""Shared I/O helpers for deterministic core modules."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def load_numeric_series(source: Sequence[float] | str | Path, *, column: str | None = None) -> list[float]:
    if isinstance(source, (str, Path)):
        return load_series_from_csv(source, column=column)

    values: list[float] = []
    for item in source:
        value = _to_float(item)
        if value is not None:
            values.append(value)
    return values


def load_series_from_csv(path: str | Path, *, column: str | None = None) -> list[float]:
    csv_path = _normalize_path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []

        selected_column = column
        values: list[float] = []
        for row in reader:
            if selected_column is None:
                for field in reader.fieldnames:
                    if _to_float(row.get(field)) is not None:
                        selected_column = field
                        break
                if selected_column is None:
                    continue
            value = _to_float(row.get(selected_column))
            if value is not None:
                values.append(value)
    return values


def load_named_matrix_from_csv(path: str | Path, *, columns: Sequence[str] | None = None) -> tuple[list[str], list[list[float]]]:
    csv_path = _normalize_path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return [], []
        selected = [name for name in columns if name in reader.fieldnames] if columns else list(reader.fieldnames)
        if not selected:
            return [], []
        series_map = {name: [] for name in selected}
        for row in reader:
            parsed_row: dict[str, float] = {}
            valid = True
            for name in selected:
                value = _to_float(row.get(name))
                if value is None:
                    valid = False
                    break
                parsed_row[name] = value
            if not valid:
                continue
            for name in selected:
                series_map[name].append(parsed_row[name])
    model_names = [name for name in selected if series_map[name]]
    return model_names, [series_map[name] for name in model_names]


def load_numeric_matrix(source: Sequence[Sequence[float]] | str | Path, *, columns: Sequence[str] | None = None) -> tuple[list[str], list[list[float]]]:
    if isinstance(source, (str, Path)):
        return load_named_matrix_from_csv(source, columns=columns)
    rows = list(source)
    if not rows:
        return [], []
    model_names: list[str] = []
    series: list[list[float]] = []
    for idx, row in enumerate(rows):
        values = [_to_float(item) for item in row]
        clean = [item for item in values if item is not None]
        if not clean:
            continue
        model_names.append(f"model_{idx}")
        series.append(clean)
    return model_names, series


def build_artifact_hints(*, artifact_dir: str | Path | None, artifact_prefix: str, names: Iterable[str]) -> dict[str, str]:
    base = Path(".") if artifact_dir is None else _normalize_path(artifact_dir)
    return {name: str(base / f"{artifact_prefix}.{name}") for name in names}
