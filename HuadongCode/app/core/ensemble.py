"""Deterministic ensemble core pipeline."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import stats

from ._io import build_artifact_hints, load_named_matrix_from_csv, load_numeric_matrix


def weighted_mean_ensemble(
    predictions: Sequence[Sequence[float]],
    weights: Sequence[float] | None = None,
) -> dict:
    n_models = len(predictions)
    if n_models == 0:
        return {"ensemble_forecast": [], "weights_used": [], "n_models": 0}

    min_len = min(len(p) for p in predictions)
    if min_len == 0:
        return {"ensemble_forecast": [], "weights_used": [], "n_models": 0}

    pred_array = np.array([list(p[:min_len]) for p in predictions], dtype=float)
    if weights is None or len(weights) != n_models:
        weights_used = np.ones(n_models) / n_models
    else:
        weight_arr = np.maximum(np.array(weights, dtype=float), 0.0)
        total = float(np.sum(weight_arr))
        weights_used = weight_arr / total if total > 0 else np.ones(n_models) / n_models

    ensemble = np.average(pred_array, axis=0, weights=weights_used)
    return {
        "ensemble_forecast": ensemble.tolist(),
        "weights_used": weights_used.tolist(),
        "n_models": n_models,
    }


def bma_ensemble(
    predictions: Sequence[Sequence[float]],
    observations: Sequence[float] | None = None,
    weights: Sequence[float] | None = None,
    window_size: int = 30,
    initial_weights: Sequence[float] | None = None,
) -> dict:
    n_models = len(predictions)
    if n_models == 0:
        return {
            "ensemble_forecast": [],
            "weights_used": [],
            "n_models": 0,
            "weight_history": [],
        }

    min_len = min(len(p) for p in predictions)
    if min_len == 0:
        return {
            "ensemble_forecast": [],
            "weights_used": [],
            "n_models": 0,
            "weight_history": [],
        }

    pred_array = np.array([list(p[:min_len]) for p in predictions], dtype=float)
    if initial_weights is not None and len(initial_weights) == n_models:
        current_weights = np.array(initial_weights, dtype=float)
    elif weights is not None and len(weights) == n_models:
        current_weights = np.array(weights, dtype=float)
    else:
        current_weights = np.ones(n_models) / n_models

    current_weights = np.maximum(current_weights, 0.01)
    current_weights = current_weights / np.sum(current_weights)

    if observations is not None:
        obs = np.array(list(observations), dtype=float)
        obs = obs[-window_size:] if len(obs) >= window_size else obs
        if len(obs) >= 2:
            pred_window = pred_array[:, -len(obs) :]
            mse_scores = np.mean((pred_window - obs) ** 2, axis=1)
            inv_mse = 1.0 / (mse_scores + 1e-6)
            current_weights = inv_mse / np.sum(inv_mse)

    ensemble = np.average(pred_array, axis=0, weights=current_weights)
    return {
        "ensemble_forecast": ensemble.tolist(),
        "weights_used": current_weights.tolist(),
        "n_models": n_models,
        "weight_history": [current_weights.tolist()],
    }


def screen_models(
    predictions: Sequence[Sequence[float]],
    observations: Sequence[float] | None = None,
    rmse_threshold: float | None = None,
    nse_threshold: float | None = None,
    bias_threshold: float | None = None,
) -> dict:
    n_models = len(predictions)
    if n_models == 0:
        return {
            "passed_models": [],
            "rejected_models": [],
            "model_metrics": {},
            "rejection_reasons": {},
        }
    if observations is None:
        return {
            "passed_models": list(range(n_models)),
            "rejected_models": [],
            "model_metrics": {},
            "rejection_reasons": {},
        }

    obs = np.array(list(observations), dtype=float)
    min_len = min([len(obs)] + [len(p) for p in predictions])
    if min_len == 0:
        return {
            "passed_models": [],
            "rejected_models": list(range(n_models)),
            "model_metrics": {},
            "rejection_reasons": {f"model_{i}": ["empty_data"] for i in range(n_models)},
        }

    obs = obs[:min_len]
    passed: list[int] = []
    rejected: list[int] = []
    metrics: dict[str, dict[str, float]] = {}
    reasons: dict[str, list[str]] = {}

    for i, pred in enumerate(predictions):
        pred_i = np.array(list(pred[:min_len]), dtype=float)
        mse = float(np.mean((pred_i - obs) ** 2))
        rmse = float(np.sqrt(mse))
        var = float(np.sum((obs - np.mean(obs)) ** 2))
        nse = float(1 - np.sum((pred_i - obs) ** 2) / var) if var > 0 else 0.0
        bias = float(np.mean(pred_i - obs))

        metrics[f"model_{i}"] = {"RMSE": rmse, "NSE": nse, "Bias": bias}
        model_reasons: list[str] = []
        if rmse_threshold is not None and rmse > rmse_threshold:
            model_reasons.append(f"RMSE={rmse:.2f} > {rmse_threshold}")
        if nse_threshold is not None and nse < nse_threshold:
            model_reasons.append(f"NSE={nse:.2f} < {nse_threshold}")
        if bias_threshold is not None and abs(bias) > bias_threshold:
            model_reasons.append(f"Bias={bias:.2f} > {bias_threshold}")

        if model_reasons:
            rejected.append(i)
            reasons[f"model_{i}"] = model_reasons
        else:
            passed.append(i)
            reasons[f"model_{i}"] = ["passed"]

    return {
        "passed_models": passed,
        "rejected_models": rejected,
        "model_metrics": metrics,
        "rejection_reasons": reasons,
    }


def consistency_check(
    predictions: Sequence[Sequence[float]],
    method: str = "kendall",
) -> dict:
    n_models = len(predictions)
    if n_models == 0:
        return {"trend_correlations": {}, "consistency_ratio": 0.0, "ensemble_mean": []}

    min_len = min(len(p) for p in predictions)
    if min_len < 3:
        return {"trend_correlations": {}, "consistency_ratio": 0.0, "ensemble_mean": []}

    pred_array = np.array([list(p[:min_len]) for p in predictions], dtype=float)
    ensemble_mean = np.mean(pred_array, axis=0)
    t = np.arange(1, min_len + 1)
    trend_correlations: dict[str, float] = {}

    for i in range(n_models):
        pred_i = pred_array[i]
        if method == "kendall":
            tau, _ = stats.kendalltau(t, pred_i)
            trend_correlations[f"model_{i}"] = float(tau) if tau is not None and not np.isnan(tau) else 0.0
        else:
            trend_correlations[f"model_{i}"] = 0.0

    positive_count = sum(1 for value in trend_correlations.values() if value > 0)
    consistency_ratio = positive_count / n_models if n_models > 0 else 0.0
    return {
        "trend_correlations": trend_correlations,
        "consistency_ratio": float(consistency_ratio),
        "ensemble_mean": ensemble_mean.tolist(),
    }


def run_ensemble_pipeline(
    *,
    predictions: Sequence[Sequence[float]] | None = None,
    predictions_path: str | None = None,
    model_columns: Sequence[str] | None = None,
    observations: Sequence[float] | None = None,
    method: str = "weighted_mean",
    weights: Sequence[float] | None = None,
    initial_weights: Sequence[float] | None = None,
    window_size: int = 30,
    rmse_threshold: float | None = None,
    nse_threshold: float | None = None,
    bias_threshold: float | None = None,
    artifact_dir: str | None = None,
    artifact_prefix: str = "ensemble",
) -> dict:
    if predictions is None and predictions_path is None:
        raise ValueError("Provide predictions or predictions_path.")

    if predictions is not None:
        model_names, matrix = load_numeric_matrix(predictions)
    else:
        model_names, matrix = load_named_matrix_from_csv(predictions_path, columns=model_columns)

    if not matrix:
        return {
            "summary_text": "No valid model prediction series were provided.",
            "selected_model_names": [],
            "screening": {
                "passed_models": [],
                "rejected_models": [],
                "model_metrics": {},
                "rejection_reasons": {},
            },
            "ensemble": {"ensemble_forecast": [], "weights_used": [], "n_models": 0},
            "consistency": {"trend_correlations": {}, "consistency_ratio": 0.0, "ensemble_mean": []},
            "artifact_hints": build_artifact_hints(
                artifact_dir=artifact_dir,
                artifact_prefix=artifact_prefix,
                names=("summary.txt", "ensemble.json"),
            ),
        }

    screening = screen_models(
        matrix,
        observations=observations,
        rmse_threshold=rmse_threshold,
        nse_threshold=nse_threshold,
        bias_threshold=bias_threshold,
    )
    selected_indices = screening["passed_models"] or list(range(len(matrix)))
    selected_predictions = [matrix[i] for i in selected_indices]
    selected_names = [model_names[i] for i in selected_indices]
    selected_weights = [weights[i] for i in selected_indices] if weights else None

    if method == "bma":
        ensemble = bma_ensemble(
            selected_predictions,
            observations=observations,
            weights=selected_weights,
            initial_weights=initial_weights,
            window_size=window_size,
        )
    else:
        ensemble = weighted_mean_ensemble(selected_predictions, weights=selected_weights)

    consistency = consistency_check(selected_predictions)
    summary_text = f"Ensembled {len(selected_names)} models using {method}; consistency={consistency['consistency_ratio']:.2f}."
    return {
        "summary_text": summary_text,
        "selected_model_names": selected_names,
        "selected_model_indices": selected_indices,
        "screening": screening,
        "ensemble": ensemble,
        "consistency": consistency,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "ensemble.json"),
        ),
    }
