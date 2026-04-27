"""Deterministic risk-analysis core pipeline."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from ._io import build_artifact_hints, load_named_matrix_from_csv, load_numeric_matrix, load_numeric_series


def exceed_probability(ensemble_predictions: Sequence[Sequence[float]], threshold: float) -> dict:
    if len(ensemble_predictions) == 0:
        return {"exceed_prob": [], "threshold": threshold, "n_ensemble": 0}
    min_len = min(len(p) for p in ensemble_predictions)
    if min_len == 0:
        return {"exceed_prob": [], "threshold": threshold, "n_ensemble": len(ensemble_predictions)}
    arr = np.array([list(p[:min_len]) for p in ensemble_predictions], dtype=float)
    exceed_counts = np.sum(arr > threshold, axis=0)
    exceed_prob = exceed_counts / arr.shape[0]
    return {"exceed_prob": exceed_prob.tolist(), "threshold": float(threshold), "n_ensemble": int(arr.shape[0])}


def quantile_risk(ensemble_predictions: Sequence[Sequence[float]], quantiles: Sequence[float] | None = None) -> dict:
    if quantiles is None:
        quantiles = [0.1, 0.25, 0.5, 0.75, 0.9]
    if len(ensemble_predictions) == 0:
        return {"quantile_values": {}, "iqr": [], "iqr_value": 0.0}
    min_len = min(len(p) for p in ensemble_predictions)
    if min_len == 0:
        return {"quantile_values": {}, "iqr": [], "iqr_value": 0.0}
    arr = np.array([list(p[:min_len]) for p in ensemble_predictions], dtype=float)
    quantile_values = {f"P{int(q * 100)}": np.percentile(arr, q * 100, axis=0).tolist() for q in quantiles}
    p25 = np.percentile(arr, 25, axis=0)
    p75 = np.percentile(arr, 75, axis=0)
    iqr = p75 - p25
    return {"quantile_values": quantile_values, "iqr": iqr.tolist(), "iqr_value": float(np.mean(iqr))}


def historical_compare(current_forecast: Sequence[float], historical_data: Sequence[float], method: str = "percentile") -> dict:
    if len(historical_data) == 0:
        return {
            "percentile_ranks": [],
            "historical_mean": 0.0,
            "historical_std": 0.0,
            "historical_percentiles": {},
            "method": method,
        }
    hist_arr = np.array(historical_data, dtype=float)
    historical_mean = float(np.mean(hist_arr))
    historical_std = float(np.std(hist_arr))
    hist_percentiles = {
        "P10": float(np.percentile(hist_arr, 10)),
        "P25": float(np.percentile(hist_arr, 25)),
        "P50": float(np.percentile(hist_arr, 50)),
        "P75": float(np.percentile(hist_arr, 75)),
        "P90": float(np.percentile(hist_arr, 90)),
    }
    percentile_ranks = [float(np.sum(hist_arr < value) / len(hist_arr) * 100.0) for value in current_forecast]
    return {
        "percentile_ranks": percentile_ranks,
        "historical_mean": historical_mean,
        "historical_std": historical_std,
        "historical_percentiles": hist_percentiles,
        "method": method,
    }


def risk_summary(ensemble_predictions: Sequence[Sequence[float]], thresholds: dict[str, float], historical_data: Sequence[float] | None = None) -> dict:
    results: dict[str, object] = {"thresholds": thresholds}
    for name, threshold in thresholds.items():
        exceed_result = exceed_probability(ensemble_predictions, threshold)
        results[f"exceed_prob_{name}"] = exceed_result["exceed_prob"]
    quantile_result = quantile_risk(ensemble_predictions)
    results["quantiles"] = quantile_result["quantile_values"]
    results["iqr"] = quantile_result["iqr_value"]
    if historical_data and len(ensemble_predictions) > 0:
        mean_forecast = np.mean(np.array(ensemble_predictions, dtype=float), axis=0).tolist()
        if mean_forecast:
            results["historical_comparison"] = historical_compare([float(np.mean(mean_forecast))], historical_data)
    return results


def run_risk_pipeline(
    *,
    ensemble_predictions: Sequence[Sequence[float]] | None = None,
    predictions_path: str | None = None,
    model_columns: Sequence[str] | None = None,
    thresholds: dict[str, float] | None = None,
    historical_data: Sequence[float] | str | None = None,
    historical_path: str | None = None,
    historical_column: str | None = None,
    artifact_dir: str | None = None,
    artifact_prefix: str = "risk",
) -> dict:
    if ensemble_predictions is None and predictions_path is None:
        raise ValueError("Provide ensemble_predictions or predictions_path.")
    if thresholds is None:
        thresholds = {}

    if ensemble_predictions is not None:
        model_names, matrix = load_numeric_matrix(ensemble_predictions)
    else:
        model_names, matrix = load_named_matrix_from_csv(predictions_path, columns=model_columns)

    if historical_data is not None:
        historical_series = load_numeric_series(historical_data, column=historical_column)
    elif historical_path is not None:
        historical_series = load_numeric_series(historical_path, column=historical_column)
    else:
        historical_series = None

    summary = risk_summary(matrix, thresholds, historical_data=historical_series)
    max_prob = 0.0
    max_prob_name = None
    for key, value in summary.items():
        if key.startswith("exceed_prob_") and isinstance(value, list) and value:
            local_max = max(value)
            if local_max > max_prob:
                max_prob = local_max
                max_prob_name = key.replace("exceed_prob_", "")

    summary_text = f"Risk computed for {len(model_names)} ensemble members." if max_prob_name is None else f"Highest exceedance risk: {max_prob_name} ({max_prob:.2f})."
    return {
        "summary_text": summary_text,
        "model_names": model_names,
        "risk": summary,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "risk.json"),
        ),
    }
