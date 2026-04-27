"""Unified model asset bundle loading and saving."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pickle

from app.core.calibrated_parameters import load_calibrated_parameter_set


REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_ASSET_DIR = REPO_ROOT / "data" / "calibrated_parameters"
MODEL_BUNDLE_PATH = MODEL_ASSET_DIR / "forecast_model_bundle.pt"


def _try_import_torch():
    try:
        import torch  # type: ignore

        return torch
    except Exception:
        return None


def preferred_bundle_serializer() -> str:
    return "torch" if _try_import_torch() is not None else "pickle_fallback"


def _torch_load(path: Path) -> dict[str, Any]:
    torch = _try_import_torch()
    if torch is None:
        with path.open("rb") as handle:
            loaded = pickle.load(handle)
    else:
        try:
            loaded = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:
            loaded = torch.load(path, map_location="cpu")
    if not isinstance(loaded, dict):
        raise TypeError(f"Expected dict model bundle, got {type(loaded)!r}")
    return loaded


def load_model_asset_bundle(path: str | Path | None = None) -> dict[str, Any]:
    bundle_path = Path(path).expanduser().resolve() if path is not None else MODEL_BUNDLE_PATH
    if not bundle_path.exists():
        return {
            "metadata": {
                "bundle_available": False,
                "bundle_path": str(bundle_path),
            },
            "hydrological": {},
            "learned_models": {},
        }
    bundle = _torch_load(bundle_path)
    metadata = dict(bundle.get("metadata", {}))
    metadata["bundle_available"] = True
    metadata["bundle_path"] = str(bundle_path)
    bundle["metadata"] = metadata
    return bundle


def save_model_asset_bundle(bundle: dict[str, Any], path: str | Path | None = None) -> Path:
    target = Path(path).expanduser().resolve() if path is not None else MODEL_BUNDLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    torch = _try_import_torch()
    if torch is None:
        with target.open("wb") as handle:
            pickle.dump(bundle, handle)
    else:
        torch.save(bundle, target)
    return target


def default_hydrological_assets() -> dict[str, Any]:
    hydrological: dict[str, Any] = {}
    for model_name in ("xaj", "gr4j"):
        param_set = load_calibrated_parameter_set(model_name)
        payload = asdict(param_set)
        payload["values"] = param_set.values.tolist()
        payload["source_path"] = str(param_set.source_path)
        hydrological[model_name] = payload
    return hydrological


def resolve_hydrological_asset(
    model_name: str,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_name = model_name.strip().lower()
    active_bundle = bundle or load_model_asset_bundle()
    bundle_assets = active_bundle.get("hydrological", {})
    if normalized_name in bundle_assets:
        asset = dict(bundle_assets[normalized_name])
        if isinstance(asset.get("values"), np.ndarray):
            asset["values"] = asset["values"].tolist()
        return asset
    param_set = load_calibrated_parameter_set(normalized_name)
    return {
        "model_name": normalized_name,
        "param_names": list(param_set.param_names),
        "values": param_set.values.tolist(),
        "normalized": bool(param_set.normalized),
        "score_name": param_set.score_name,
        "score_value": param_set.score_value,
        "source_path": str(param_set.source_path),
    }


def resolve_learned_model_asset(
    model_name: str,
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    active_bundle = bundle or load_model_asset_bundle()
    learned = active_bundle.get("learned_models", {})
    asset = learned.get(model_name)
    return dict(asset) if isinstance(asset, dict) else asset


def describe_model_asset_bundle(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    active_bundle = bundle or load_model_asset_bundle()
    hydrological = active_bundle.get("hydrological", {})
    learned = active_bundle.get("learned_models", {})
    return {
        "metadata": dict(active_bundle.get("metadata", {})),
        "hydrological_models": sorted(hydrological.keys()),
        "learned_models": sorted(learned.keys()),
    }
