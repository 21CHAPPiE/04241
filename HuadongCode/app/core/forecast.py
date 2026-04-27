"""Forecast core pipeline with deterministic artifact-friendly outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from app.core.data_loading import load_basin_dataset
from app.core.model_assets import load_model_asset_bundle, resolve_hydrological_asset, resolve_learned_model_asset
from app.core.trained_models import predict_with_lstm_asset, predict_with_rf_asset
from app.domain import ForecastFrame

from ._io import build_artifact_hints
from .gr4j_model import GR4JModelRunner
from .xaj_model import XAJModelRunner


class XinanjiangModel:
    def __init__(self, basin_area_km2: float = 3300.0, warmup_length: int = 0) -> None:
        self.runner = XAJModelRunner(
            basin_area_km2=basin_area_km2,
            time_interval_hours=1,
            warmup_length=warmup_length,
        )

    def forward(self, rainfall: Sequence[float], pet: Sequence[float], params: Sequence[float] | None = None) -> list[float]:
        return self.runner.predict(rainfall=rainfall, pet=pet, params=params)


class GR4JModel:
    def __init__(self, basin_area_km2: float = 3300.0, warmup_length: int = 0) -> None:
        self.runner = GR4JModelRunner(
            basin_area_km2=basin_area_km2,
            warmup_length=warmup_length,
        )

    def forward(self, rainfall: Sequence[float], pet: Sequence[float], params: Sequence[float] | None = None) -> list[float]:
        return self.runner.predict(rainfall=rainfall, pet=pet, params=params)


def _rf_like_forecast(rainfall: Sequence[float], observed: Sequence[float]) -> list[float]:
    rain = np.array(rainfall, dtype=float)
    obs = np.array(observed, dtype=float)
    n = len(rain)
    if n == 0:
        return []
    feats = []
    for i in range(n):
        prev_rain = rain[i - 1] if i > 0 else 0.0
        prev_obs = obs[i - 1] if i > 0 else obs[0]
        feats.append([1.0, rain[i], prev_rain, prev_obs])
    X = np.array(feats, dtype=float)
    coeffs, *_ = np.linalg.lstsq(X, obs, rcond=None)
    pred = X @ coeffs
    return np.maximum(pred, 0.0).tolist()


def _lstm_like_forecast(rainfall: Sequence[float], observed: Sequence[float]) -> list[float]:
    rain = np.array(rainfall, dtype=float)
    obs = np.array(observed, dtype=float)
    last_values = list(obs[:3]) if len(obs) >= 3 else list(obs) or [0.0, 0.0, 0.0]
    trend = float(np.mean(np.diff(obs[-3:]))) if len(obs) >= 4 else 0.0
    preds: list[float] = []
    rain_factor = float(np.mean(rain) * 0.5) if len(rain) > 0 else 0.0
    for value in rain:
        base = float(np.mean(last_values)) if last_values else 0.0
        pred = max(base * 0.7 + value * 0.3 + rain_factor * 0.3 + trend * 0.1, 0.0)
        preds.append(float(pred))
        last_values.append(pred)
        last_values = last_values[-3:]
    return preds


def _metrics(pred: Sequence[float], obs: Sequence[float]) -> dict[str, float | None]:
    if not pred or not obs:
        return {"RMSE": None, "NSE": None, "Bias": None}
    n = min(len(pred), len(obs))
    pred_arr = np.array(pred[:n], dtype=float)
    obs_arr = np.array(obs[:n], dtype=float)
    mse = float(np.mean((pred_arr - obs_arr) ** 2))
    var = float(np.sum((obs_arr - np.mean(obs_arr)) ** 2))
    return {
        "RMSE": float(np.sqrt(mse)),
        "NSE": float(1 - np.sum((pred_arr - obs_arr) ** 2) / var) if var > 0 else None,
        "Bias": float(np.mean(pred_arr - obs_arr)),
    }


def run_forecast_pipeline(
    *,
    dataset_path: str | Path,
    artifact_dir: str | None = None,
    artifact_prefix: str = "forecast",
) -> dict:
    dataset = load_basin_dataset(dataset_path)
    timestamps = dataset.timestamps
    rainfall = dataset.rainfall
    pet = dataset.pet
    observed = dataset.streamflow
    pet_series = pet if pet else [0.0] * len(rainfall)
    asset_bundle = load_model_asset_bundle()

    xaj_asset = resolve_hydrological_asset("xaj", asset_bundle)
    gr4j_asset = resolve_hydrological_asset("gr4j", asset_bundle)
    xaj = XinanjiangModel().forward(rainfall, pet_series, params=xaj_asset.get("values"))
    gr4j = GR4JModel().forward(rainfall, pet_series, params=gr4j_asset.get("values"))
    rf = predict_with_rf_asset(resolve_learned_model_asset("rf", asset_bundle), rainfall, pet_series, observed)
    if rf is None:
        rf = _rf_like_forecast(rainfall, observed)
    lstm = predict_with_lstm_asset(resolve_learned_model_asset("lstm", asset_bundle), rainfall, pet_series, observed)
    if lstm is None:
        lstm = _lstm_like_forecast(rainfall, observed)

    metrics = {
        "xinanjiang": _metrics(xaj, observed),
        "gr4j": _metrics(gr4j, observed),
        "rf": _metrics(rf, observed),
        "lstm": _metrics(lstm, observed),
    }
    summary = (
        f"Forecasted {len(timestamps)} steps with 4 models; "
        f"best RMSE={min(v['RMSE'] for v in metrics.values() if v['RMSE'] is not None):.2f}."
        if timestamps
        else "No forecast data available."
    )

    return {
        "summary_text": summary,
        "frame": ForecastFrame(
            timestamps=timestamps,
            rainfall=rainfall,
            pet=pet_series,
            observed=observed,
            xinanjiang=xaj,
            gr4j=gr4j,
            rf=rf,
            lstm=lstm,
        ),
        "metrics": metrics,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "forecast.csv", "forecast-metrics.json"),
        ),
    }
