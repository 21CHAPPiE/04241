"""Deterministic data-analysis core pipeline."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import stats
from scipy.fft import fft, fftfreq

from ._io import build_artifact_hints, load_numeric_series


def trend_analysis(values: Sequence[float]) -> dict:
    n = len(values)
    if n < 2:
        return {
            "trend_direction": "no_trend",
            "kendall_tau": 0.0,
            "p_value": 1.0,
            "significant": False,
            "slope": 0.0,
            "intercept": 0.0,
        }

    arr = np.array(values, dtype=float)
    t = np.arange(1, n + 1)
    tau, p_value = stats.kendalltau(t, arr)
    tau_value = 0.0 if tau is None or np.isnan(tau) else float(tau)
    p_val = 1.0 if p_value is None or np.isnan(p_value) else float(p_value)
    slope, intercept, _, _, _ = stats.linregress(t, arr)

    if p_val < 0.05 and slope > 0:
        direction = "increasing"
    elif p_val < 0.05 and slope < 0:
        direction = "decreasing"
    else:
        direction = "no_trend"

    return {
        "trend_direction": direction,
        "kendall_tau": tau_value,
        "p_value": p_val,
        "significant": bool(p_val < 0.05),
        "slope": float(slope),
        "intercept": float(intercept),
    }


def cycle_analysis(values: Sequence[float], timestep_hours: float = 1.0) -> dict:
    n = len(values)
    if n < 4:
        return {
            "dominant_period_hours": 0.0,
            "dominant_period_days": 0.0,
            "top_frequencies": [],
            "top_periods_hours": [],
            "top_powers": [],
        }

    arr = np.array(values, dtype=float)
    arr = arr - np.mean(arr)
    yf = np.abs(fft(arr))[: n // 2]
    freqs = fftfreq(n, d=timestep_hours)[: n // 2]
    valid_mask = freqs > 0
    freqs = freqs[valid_mask]
    yf = yf[valid_mask]
    if len(yf) == 0:
        return {
            "dominant_period_hours": 0.0,
            "dominant_period_days": 0.0,
            "top_frequencies": [],
            "top_periods_hours": [],
            "top_powers": [],
        }

    top_indices = np.argsort(yf)[::-1][:10]
    top_freqs = freqs[top_indices].tolist()
    top_powers = yf[top_indices].tolist()
    top_periods = [1.0 / f if f > 0 else 0.0 for f in top_freqs]
    dominant_period_hours = top_periods[0] if top_periods else 0.0
    return {
        "dominant_period_hours": float(dominant_period_hours),
        "dominant_period_days": float(dominant_period_hours / 24.0),
        "top_frequencies": top_freqs[:10],
        "top_periods_hours": top_periods[:10],
        "top_powers": top_powers[:10],
    }


def mutation_detection(values: Sequence[float]) -> dict:
    n = len(values)
    if n < 4:
        return {
            "has_mutation": False,
            "change_point_index": None,
            "change_point_timestamp": None,
            "p_value": 1.0,
            "statistic": 0.0,
            "mean_before": None,
            "mean_after": None,
        }

    arr = np.array(values, dtype=float)
    ranks = stats.rankdata(arr)
    u_values = np.array(
        [2.0 * np.sum(ranks[: k + 1]) - (k + 1) * (n + 1) for k in range(n)],
        dtype=float,
    )
    max_u = float(np.max(np.abs(u_values)))
    change_point_index = int(np.argmax(np.abs(u_values)))
    p_value = float(2.0 * np.exp((-6.0 * max_u**2) / (n**3 + n**2)))
    has_mutation = p_value < 0.05 and 0 < change_point_index < n - 1
    if has_mutation:
        mean_before = float(np.mean(arr[:change_point_index]))
        mean_after = float(np.mean(arr[change_point_index:]))
    else:
        mean_before = None
        mean_after = None
        change_point_index = None

    return {
        "has_mutation": has_mutation,
        "change_point_index": change_point_index,
        "change_point_timestamp": None,
        "p_value": p_value,
        "statistic": max_u,
        "mean_before": mean_before,
        "mean_after": mean_after,
    }


def generate_summary_text(
    *,
    station_id: str,
    variable: str,
    trend_result: dict,
    cycle_result: dict,
    mutation_result: dict,
    n_samples: int,
    value_mean: float,
    value_std: float,
) -> str:
    trend = trend_result.get("trend_direction", "no_trend")
    trend_sig = trend_result.get("significant", False)
    cycle_days = float(cycle_result.get("dominant_period_days", 0.0) or 0.0)
    mutation = bool(mutation_result.get("has_mutation", False))
    parts = [
        f"{station_id}/{variable}: n={n_samples}, mean={value_mean:.2f}, std={value_std:.2f}.",
        f"Trend={trend}{' (significant)' if trend_sig else ' (not significant)'}.",
    ]
    if cycle_days > 0:
        parts.append(f"Dominant cycle ~{cycle_days:.1f} days.")
    parts.append("Mutation detected." if mutation else "No significant mutation.")
    return " ".join(parts)


def run_data_analysis_pipeline(
    *,
    values: Sequence[float] | str | None = None,
    dataset_path: str | None = None,
    value_column: str | None = None,
    station_id: str = "unknown",
    variable: str = "streamflow",
    timestep_hours: float = 1.0,
    artifact_dir: str | None = None,
    artifact_prefix: str = "data_analysis",
) -> dict:
    if values is None and dataset_path is None:
        raise ValueError("Provide values or dataset_path.")

    source = values if values is not None else dataset_path
    series = load_numeric_series(source, column=value_column)
    n_samples = len(series)
    if n_samples == 0:
        return {
            "summary_text": "No valid numeric samples were provided.",
            "series_stats": {"n_samples": 0, "mean": None, "std": None, "min": None, "max": None},
            "trend": trend_analysis([]),
            "cycle": cycle_analysis([], timestep_hours=timestep_hours),
            "mutation": mutation_detection([]),
            "artifact_hints": build_artifact_hints(
                artifact_dir=artifact_dir,
                artifact_prefix=artifact_prefix,
                names=("summary.txt", "analysis.json"),
            ),
        }

    arr = np.array(series, dtype=float)
    series_stats = {
        "n_samples": n_samples,
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }
    trend = trend_analysis(series)
    cycle = cycle_analysis(series, timestep_hours=timestep_hours)
    mutation = mutation_detection(series)
    summary_text = generate_summary_text(
        station_id=station_id,
        variable=variable,
        trend_result=trend,
        cycle_result=cycle,
        mutation_result=mutation,
        n_samples=n_samples,
        value_mean=series_stats["mean"],
        value_std=series_stats["std"],
    )
    return {
        "summary_text": summary_text,
        "series_stats": series_stats,
        "trend": trend,
        "cycle": cycle,
        "mutation": mutation,
        "artifact_hints": build_artifact_hints(
            artifact_dir=artifact_dir,
            artifact_prefix=artifact_prefix,
            names=("summary.txt", "analysis.json"),
        ),
    }
