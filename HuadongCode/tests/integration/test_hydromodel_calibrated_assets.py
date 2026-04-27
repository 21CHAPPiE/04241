from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from app.core.calibrated_parameters import load_calibrated_parameter_set
from app.core.gr4j_model import GR4JModelRunner
from app.core.xaj_model import XAJModelRunner
from app.tools.forecast import run_forecast_from_paths


def _load_series(path: Path, limit: int = 240) -> tuple[list[float], list[float]]:
    rainfall: list[float] = []
    pet: list[float] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if idx >= limit:
                break
            rainfall.append(float(row["precipitation"]))
            pet.append(float(row["potential_evapotranspiration"]))
    return rainfall, pet


def test_calibrated_parameter_assets_load_for_both_models() -> None:
    xaj = load_calibrated_parameter_set("xaj")
    gr4j = load_calibrated_parameter_set("gr4j")

    assert xaj.normalized is True
    assert xaj.values.shape == (15,)
    assert xaj.score_value is not None
    assert xaj.source_path.exists()

    assert gr4j.normalized is False
    assert gr4j.values.shape == (4,)
    assert gr4j.values[3] > 10.0
    assert gr4j.score_value is not None
    assert gr4j.source_path.exists()


def test_calibrated_runners_produce_finite_series(sample_basin_csv: Path) -> None:
    rainfall, pet = _load_series(sample_basin_csv)

    xaj_pred = XAJModelRunner().predict(rainfall=rainfall, pet=pet)
    gr4j_pred = GR4JModelRunner().predict(rainfall=rainfall, pet=pet)

    assert len(xaj_pred) == len(rainfall)
    assert len(gr4j_pred) == len(rainfall)
    assert np.isfinite(np.asarray(xaj_pred, dtype=float)).all()
    assert np.isfinite(np.asarray(gr4j_pred, dtype=float)).all()
    assert max(xaj_pred) > 0.0
    assert max(gr4j_pred) > 0.0


def test_forecast_tool_writes_gr4j_column(
    sample_basin_csv: Path,
    artifact_dir: Path,
) -> None:
    result = run_forecast_from_paths(
        dataset_path=str(sample_basin_csv),
        output_root=str(artifact_dir),
    )

    forecast_csv = Path(result["artifact_paths"]["forecast"])
    with forecast_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames is not None
        assert "forecast_gr4j" in reader.fieldnames
