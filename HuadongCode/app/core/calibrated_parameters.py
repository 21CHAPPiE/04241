"""Load calibrated hydrological parameter assets from checked-in files."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
CALIBRATED_PARAMETER_DIR = REPO_ROOT / "data" / "calibrated_parameters"


@dataclass(frozen=True)
class CalibratedParameterSet:
    model_name: str
    param_names: tuple[str, ...]
    values: np.ndarray
    normalized: bool
    score_name: str | None
    score_value: float | None
    source_path: Path


_MODEL_SPECS = {
    "xaj": {
        "canonical_path": CALIBRATED_PARAMETER_DIR / "xaj_best_parameters.csv",
        "legacy_path": REPO_ROOT / "old_code" / "XAJ" / "XAJ_Best_Parameters.csv",
        "param_names": (
            "K",
            "B",
            "IM",
            "UM",
            "LM",
            "DM",
            "C",
            "SM",
            "EX",
            "KI",
            "KG",
            "CS",
            "L",
            "CI",
            "CG",
        ),
        "normalized": True,
    },
    "gr4j": {
        "canonical_path": CALIBRATED_PARAMETER_DIR / "gr4j_best_parameters.csv",
        "legacy_path": REPO_ROOT / "old_code" / "GR4J" / "GR4J_best_Parameter.csv",
        "param_names": ("x1", "x2", "x3", "x4"),
        "normalized": False,
    },
}


def _read_text_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _read_legacy_excel_rows(path: Path) -> list[dict[str, str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                texts = [node.text or "" for node in si.findall(".//a:t", ns)]
                shared.append("".join(texts))

        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        raw_rows: list[list[str]] = []
        for row in sheet.findall("a:sheetData/a:row", ns):
            values: list[str] = []
            for cell in row.findall("a:c", ns):
                cell_type = cell.get("t")
                node = cell.find("a:v", ns)
                if node is None or node.text is None:
                    values.append("")
                elif cell_type == "s":
                    values.append(shared[int(node.text)])
                else:
                    values.append(node.text)
            raw_rows.append(values)

    if not raw_rows:
        return []

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(raw_rows)
    buffer.seek(0)
    return [dict(row) for row in csv.DictReader(buffer)]


def _read_parameter_rows(path: Path) -> list[dict[str, str]]:
    try:
        return _read_text_csv_rows(path)
    except UnicodeDecodeError:
        return _read_legacy_excel_rows(path)
    except csv.Error:
        return _read_legacy_excel_rows(path)


def _normalize_key(text: str | None) -> str:
    return (text or "").strip().lower()


def _ordered_values(
    rows: Iterable[dict[str, str]],
    expected_names: tuple[str, ...],
) -> tuple[np.ndarray, str | None, float | None]:
    values_by_name: dict[str, float] = {}
    score_name: str | None = None
    score_value: float | None = None

    for row in rows:
        key = row.get("Parameter") or row.get("parameter") or row.get("name") or ""
        value = row.get("Best_Value") or row.get("best_value") or row.get("value") or ""
        if key == "" or value == "":
            continue
        normalized_key = _normalize_key(key)
        if normalized_key.startswith("best_") or normalized_key.endswith("_nse"):
            score_name = key.strip()
            score_value = float(value)
            continue
        values_by_name[normalized_key] = float(value)

    ordered = []
    for name in expected_names:
        normalized_name = _normalize_key(name)
        if normalized_name not in values_by_name:
            raise KeyError(f"Missing calibrated parameter '{name}'")
        ordered.append(values_by_name[normalized_name])

    return np.asarray(ordered, dtype=float), score_name, score_value


def _resolve_source_path(model_name: str) -> Path:
    spec = _MODEL_SPECS[model_name]
    for key in ("canonical_path", "legacy_path"):
        path = Path(spec[key])
        if path.exists():
            return path
    raise FileNotFoundError(f"No calibrated parameter asset found for {model_name}")


@lru_cache(maxsize=None)
def load_calibrated_parameter_set(model_name: str) -> CalibratedParameterSet:
    normalized_name = model_name.strip().lower()
    if normalized_name not in _MODEL_SPECS:
        raise KeyError(f"Unsupported model '{model_name}'")

    spec = _MODEL_SPECS[normalized_name]
    source_path = _resolve_source_path(normalized_name)
    rows = _read_parameter_rows(source_path)
    values, score_name, score_value = _ordered_values(rows, spec["param_names"])
    return CalibratedParameterSet(
        model_name=normalized_name,
        param_names=tuple(spec["param_names"]),
        values=values,
        normalized=bool(spec["normalized"]),
        score_name=score_name,
        score_value=score_value,
        source_path=source_path,
    )


def load_calibrated_parameters(model_name: str) -> tuple[np.ndarray, bool]:
    param_set = load_calibrated_parameter_set(model_name)
    return param_set.values.copy(), param_set.normalized
