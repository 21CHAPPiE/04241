"""Deterministic error-analysis and correction-summary core pipeline."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ._io import build_artifact_hints, load_numeric_series


def compute_error_metrics(predictions: Sequence[float], observations: Sequence[float]) -> dict:
    if len(predictions) != len(observations) or len(predictions) == 0:
        return {
            "RMSE": None,
            "MAE": None,
            "NSE": None,
            "Bias": None,
            "Correlation": None,
            "peak_error": None,
            "peak_time_error": None,
        }

    pred = np.array(predictions, dtype=float)
    obs = np.array(observations, dtype=float)
    mse = np.mean((pred - obs) ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(pred - obs))
    var = np.sum((obs - np.mean(obs)) ** 2)
    nse = 1 - np.sum((pred - obs) ** 2) / var if var > 0 else 0.0
    bias = np.mean(pred - obs)
    if len(pred) > 1:
        corr = float(np.corrcoef(pred, obs)[0, 1])
        if np.isnan(corr):
            corr = None
    else:
        corr = None
    pred_peak_idx = int(np.argmax(pred))
    obs_peak_idx = int(np.argmax(obs))
    peak_error = float(abs(pred[pred_peak_idx] - obs[obs_peak_idx]))
    peak_time_error = abs(pred_peak_idx - obs_peak_idx)
    return {
        "RMSE": float(rmse),
        "MAE": float(mae),
        "NSE": float(nse),
        "Bias": float(bias),
        "Correlation": corr,
        "peak_error": peak_error,
        "peak_time_error": int(peak_time_error),
    }


def sliding_window_error(
    predictions: Sequence[float],
    observations: Sequence[float],
    window_size: int = 24,
    step: int = 1,
) -> dict:
    if len(predictions) != len(observations) or len(predictions) < window_size:
        return {
            "error_series": [],
            "error_means": [],
            "error_stds": [],
            "drift_detected": False,
            "drift_points": [],
        }

    pred = np.array(predictions, dtype=float)
    obs = np.array(observations, dtype=float)
    errors = pred - obs
    error_means: list[float] = []
    error_stds: list[float] = []
    for i in range(0, len(errors) - window_size + 1, step):
        window = errors[i : i + window_size]
        error_means.append(float(np.mean(window)))
        error_stds.append(float(np.std(window)))

    error_arr = np.array(error_means, dtype=float)
    if len(error_arr) > 2:
        mean_err = float(np.mean(error_arr))
        std_err = float(np.std(error_arr))
        drift_points = [
            idx * step
            for idx, value in enumerate(error_arr)
            if std_err > 0 and abs(value - mean_err) > 2 * std_err
        ]
        drift_detected = len(drift_points) > 0
    else:
        drift_detected = False
        drift_points = []

    return {
        "error_series": error_means,
        "error_means": error_means,
        "error_stds": error_stds,
        "drift_detected": drift_detected,
        "drift_points": drift_points,
    }


def anomaly_detection(
    predictions: Sequence[float],
    observations: Sequence[float],
    threshold_sigma: float = 3.0,
) -> dict:
    if len(predictions) != len(observations) or len(predictions) == 0:
        return {"anomaly_indices": [], "anomaly_types": [], "anomaly_timestamps": []}

    pred = np.array(predictions, dtype=float)
    obs = np.array(observations, dtype=float)
    errors = pred - obs
    mean_error = float(np.mean(errors))
    std_error = float(np.std(errors))
    if std_error < 1e-6:
        return {"anomaly_indices": [], "anomaly_types": [], "anomaly_timestamps": []}

    threshold = threshold_sigma * std_error
    anomaly_indices: list[int] = []
    anomaly_types: list[str] = []
    for i, err in enumerate(errors):
        if abs(err - mean_error) > threshold:
            is_spike = i > 0 and abs(errors[i] - errors[i - 1]) > threshold
            anomaly_types.append("spike" if is_spike else "drift")
            anomaly_indices.append(int(i))

    return {
        "anomaly_indices": anomaly_indices,
        "anomaly_types": anomaly_types,
        "anomaly_timestamps": anomaly_indices,
    }


def build_error_correction_summary(metrics: dict, anomaly_info: dict) -> dict:
    recommendations: list[str] = []
    nse = metrics.get("NSE")
    bias = metrics.get("Bias")
    peak_error = metrics.get("peak_error")

    if nse is not None:
        if nse < 0:
            recommendations.append("Recalibrate model parameters; baseline outperforms current model.")
        elif nse < 0.5:
            recommendations.append("Add predictive features or refine model structure.")
    if bias is not None:
        if bias > 0:
            recommendations.append("Apply negative bias correction to reduce systematic over-forecasting.")
        elif bias < 0:
            recommendations.append("Apply positive bias correction to reduce systematic under-forecasting.")
    if peak_error is not None and peak_error > 0:
        recommendations.append("Tune peak handling; peak error remains non-zero.")

    anomalies = anomaly_info.get("anomaly_indices", [])
    if anomalies:
        spike_count = anomaly_info.get("anomaly_types", []).count("spike")
        drift_count = anomaly_info.get("anomaly_types", []).count("drift")
        recommendations.append(f"Validate data quality around anomalies (spike={spike_count}, drift={drift_count}).")

    summary = " ".join(recommendations) if recommendations else "No major correction actions suggested."
    return {"summary_text": summary, "recommendations": recommendations}


def run_error_analysis_pipeline(
    *,
    predictions: Sequence[float] | str | None = None,
    observations: Sequence[float] | str | None = None,
    dataset_path: str | None = None,
    prediction_column: str = "prediction",
    observation_column: str = "observation",
    window_size: int = 24,
    step: int = 1,
    threshold_sigma: float = 3.0,
    artifact_dir: str | None = None,
    artifact_prefix: str = "error_analysis",
) -> dict:
    if dataset_path is not None:
        pred = load_numeric_series(dataset_path, column=prediction_column)
        obs = load_numeric_series(dataset_path, column=observation_column)
    else:
        if predictions is None or observations is None:
            raise ValueError("Provide predictions and observations, or provide dataset_path with columns.")
        pred = load_numeric_series(predictions)
        obs = load_numeric_series(observations)

    min_len = min(len(pred), len(obs))
    pred = pred[:min_len]
    obs = obs[:min_len]
    metrics = compute_error_metrics(pred, obs)
    window = sliding_window_error(pred, obs, window_size=window_size, step=step)
    anomaly = anomaly_detection(pred, obs, threshold_sigma=threshold_sigma)
    correction = build_error_correction_summary(metrics, anomaly)

    short_metrics = []
    for key in ("NSE", "Bias", "RMSE"):
        value = metrics.get(key)
        if value is not None:
            short_metrics.append(f"{key}={value:.3f}" if key == "NSE" else f"{key}={value:.2f}")
    summary = f"Error metrics: {', '.join(short_metrics)}. {correction['summary_text']}" if short_metrics else correction["summary_text"]

    return {
        "summary_text": summary,
        "error_metrics": metrics,
        "window_analysis": window,
        "anomaly_info": anomaly,
        "correction_summary": correction,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "error-analysis.json"),
        ),
    }
