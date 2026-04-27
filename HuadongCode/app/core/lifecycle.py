"""Lifecycle smoke pipelines for training, calibration, and HPO."""

from __future__ import annotations

import csv
import pickle
from pathlib import Path
from typing import Sequence

import numpy as np

from ._io import build_artifact_hints


def _load_basin_arrays(dataset_path: str | Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = Path(dataset_path).expanduser().resolve()
    precipitation: list[float] = []
    pet: list[float] = []
    streamflow: list[float] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            precipitation.append(float(row.get("precipitation", 0.0) or 0.0))
            pet.append(float(row.get("potential_evapotranspiration", 0.0) or 0.0))
            streamflow.append(float(row.get("streamflow", 0.0) or 0.0))
    return np.array(precipitation, dtype=float), np.array(pet, dtype=float), np.array(streamflow, dtype=float)


def run_training_pipeline(
    *,
    dataset_path: str | Path,
    artifact_dir: str | None = None,
    artifact_prefix: str = "training",
) -> dict:
    rain, pet, flow = _load_basin_arrays(dataset_path)
    if len(flow) == 0:
        raise ValueError("dataset_path did not contain any training rows")
    X = np.column_stack([np.ones(len(flow)), rain, pet])
    coeffs, *_ = np.linalg.lstsq(X, flow, rcond=None)
    preds = X @ coeffs
    rmse = float(np.sqrt(np.mean((preds - flow) ** 2)))
    model_state = {
        "model_type": "linear_regression_smoke",
        "weights": coeffs.tolist(),
        "rmse": rmse,
        "n_rows": int(len(flow)),
    }
    return {
        "summary_text": f"Training smoke completed on {len(flow)} rows; RMSE={rmse:.2f}.",
        "model_state": model_state,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "training.json", "model.pt"),
        ),
    }


def run_calibration_pipeline(
    *,
    dataset_path: str | Path,
    artifact_dir: str | None = None,
    artifact_prefix: str = "calibration",
) -> dict:
    rain, _pet, flow = _load_basin_arrays(dataset_path)
    params = {
        "im": float(np.clip(np.mean(rain) / (np.std(rain) + 1e-6), 0.1, 5.0)),
        "um": float(max(np.percentile(rain, 75), 1.0)),
        "lm": float(max(np.percentile(flow, 25), 1.0)),
        "dm": float(max(np.percentile(flow, 10), 1.0)),
        "b": float(np.clip(np.std(flow) / (np.mean(flow) + 1e-6), 0.1, 2.0)),
    }
    return {
        "summary_text": f"Calibration smoke derived {len(params)} parameters from {len(flow)} rows.",
        "parameters": params,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "calibration.json"),
        ),
    }


def run_hpo_pipeline(
    *,
    dataset_path: str | Path,
    artifact_dir: str | None = None,
    artifact_prefix: str = "hpo",
    candidate_alphas: Sequence[float] | None = None,
) -> dict:
    rain, pet, flow = _load_basin_arrays(dataset_path)
    if candidate_alphas is None:
        candidate_alphas = [0.25, 0.5, 0.75, 1.0, 1.25]
    best = None
    for alpha in candidate_alphas:
        pred = alpha * rain + 0.1 * pet
        rmse = float(np.sqrt(np.mean((pred - flow) ** 2)))
        trial = {"alpha": float(alpha), "rmse": rmse}
        if best is None or rmse < best["rmse"]:
            best = trial
    assert best is not None
    return {
        "summary_text": f"HPO smoke selected alpha={best['alpha']:.2f} with RMSE={best['rmse']:.2f}.",
        "best_result": best,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "hpo.json"),
        ),
    }


def save_training_model(path: str | Path, model_state: dict) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as handle:
        pickle.dump(model_state, handle)
    return target
