"""Dataset loading interfaces with schema compatibility for forecast workflows."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class BasinDataset:
    source_path: Path | None
    schema_name: str
    field_names: tuple[str, ...]
    timestamps: list[str]
    rainfall: list[float]
    pet: list[float]
    streamflow: list[float]


@dataclass(frozen=True)
class MultiStationDataset:
    source_path: Path | None
    schema_name: str
    field_names: tuple[str, ...]
    timestamps: list[str]
    runoff: list[float]
    station_columns: tuple[str, ...]
    station_values: dict[str, list[float]]


def _normalize_key(text: str) -> str:
    return text.strip().lower().replace(" ", "_")


def _select_column(
    field_names: Sequence[str],
    aliases: Sequence[str],
    explicit_name: str | None = None,
) -> str | None:
    if explicit_name is not None and explicit_name in field_names:
        return explicit_name
    normalized = {_normalize_key(name): name for name in field_names}
    for alias in aliases:
        match = normalized.get(_normalize_key(alias))
        if match is not None:
            return match
    return None


def _read_rows_from_path(path: str | Path) -> tuple[Path, list[dict[str, Any]]]:
    resolved = Path(path).expanduser().resolve()
    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return resolved, [dict(row) for row in reader]


def _rows_from_source(
    source: str | Path | Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
) -> tuple[Path | None, list[dict[str, Any]]]:
    if isinstance(source, (str, Path)):
        return _read_rows_from_path(source)
    if isinstance(source, Mapping):
        keys = list(source.keys())
        if not keys:
            return None, []
        length = len(source[keys[0]])
        rows = []
        for idx in range(length):
            rows.append({key: source[key][idx] for key in keys})
        return None, rows
    rows = [dict(row) for row in source]
    return None, rows


def load_basin_dataset(
    source: str | Path | Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
    *,
    column_map: Mapping[str, str] | None = None,
) -> BasinDataset:
    source_path, rows = _rows_from_source(source)
    if not rows:
        raise ValueError("No rows available for basin dataset loading")

    field_names = tuple(rows[0].keys())
    time_column = _select_column(field_names, ("time", "timestamp", "datetime", "Time"), column_map.get("time") if column_map else None)
    rainfall_column = _select_column(field_names, ("precipitation", "rainfall", "rain"), column_map.get("rainfall") if column_map else None)
    pet_column = _select_column(field_names, ("potential_evapotranspiration", "pet", "evaporation"), column_map.get("pet") if column_map else None)
    streamflow_column = _select_column(field_names, ("streamflow", "runoff", "observed"), column_map.get("streamflow") if column_map else None)

    if time_column is None or rainfall_column is None or streamflow_column is None:
        raise KeyError(
            "Basin dataset requires compatible time/rainfall/streamflow columns"
        )

    timestamps: list[str] = []
    rainfall: list[float] = []
    pet: list[float] = []
    streamflow: list[float] = []
    for row in rows:
        timestamps.append(str(row[time_column]))
        rainfall.append(float(row[rainfall_column] or 0.0))
        pet.append(float(row[pet_column] or 0.0) if pet_column is not None else 0.0)
        streamflow.append(float(row[streamflow_column] or 0.0))

    return BasinDataset(
        source_path=source_path,
        schema_name="basin_hourly",
        field_names=field_names,
        timestamps=timestamps,
        rainfall=rainfall,
        pet=pet,
        streamflow=streamflow,
    )


def load_multistation_dataset(
    source: str | Path | Sequence[Mapping[str, Any]] | Mapping[str, Sequence[Any]],
    *,
    column_map: Mapping[str, str] | None = None,
) -> MultiStationDataset:
    source_path, rows = _rows_from_source(source)
    if not rows:
        raise ValueError("No rows available for multi-station dataset loading")

    field_names = tuple(rows[0].keys())
    time_column = _select_column(field_names, ("Time", "time", "timestamp"), column_map.get("time") if column_map else None)
    runoff_column = _select_column(field_names, ("Runoff", "runoff", "streamflow"), column_map.get("runoff") if column_map else None)
    if time_column is None or runoff_column is None:
        raise KeyError("Multi-station dataset requires compatible time/runoff columns")

    station_columns = tuple(
        name for name in field_names if name not in {time_column, runoff_column}
    )
    timestamps: list[str] = []
    runoff: list[float] = []
    station_values: dict[str, list[float]] = {name: [] for name in station_columns}

    for row in rows:
        timestamps.append(str(row[time_column]))
        runoff.append(float(row[runoff_column] or 0.0))
        for name in station_columns:
            raw = row.get(name)
            station_values[name].append(float(raw) if raw not in (None, "") else 0.0)

    return MultiStationDataset(
        source_path=source_path,
        schema_name="multistation_hourly",
        field_names=field_names,
        timestamps=timestamps,
        runoff=runoff,
        station_columns=station_columns,
        station_values=station_values,
    )


def describe_dataset(dataset: BasinDataset | MultiStationDataset) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_name": dataset.schema_name,
        "source_path": str(dataset.source_path) if dataset.source_path is not None else None,
        "field_names": list(dataset.field_names),
        "n_rows": len(dataset.timestamps),
        "time_start": dataset.timestamps[0] if dataset.timestamps else None,
        "time_end": dataset.timestamps[-1] if dataset.timestamps else None,
    }
    if isinstance(dataset, BasinDataset):
        payload.update(
            {
                "series": {
                    "rainfall": len(dataset.rainfall),
                    "pet": len(dataset.pet),
                    "streamflow": len(dataset.streamflow),
                }
            }
        )
    else:
        payload.update(
            {
                "series": {
                    "runoff": len(dataset.runoff),
                },
                "station_columns": list(dataset.station_columns),
                "n_stations": len(dataset.station_columns),
            }
        )
    return payload

