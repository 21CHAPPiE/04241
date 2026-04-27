"""Training and inference helpers for learned forecast assets."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neural_network import MLPRegressor

from app.core.data_loading import load_basin_dataset
from app.core.model_assets import default_hydrological_assets, preferred_bundle_serializer, save_model_asset_bundle


FEATURE_NAMES = (
    "rain_t",
    "pet_t",
    "rain_t_minus_1",
    "pet_t_minus_1",
    "flow_t_minus_1",
    "flow_t_minus_2",
    "flow_t_minus_3",
)


def _rmse(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((pred - target) ** 2)))


def build_tabular_features(
    rainfall: list[float],
    pet: list[float],
    streamflow: list[float],
    history: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    rain = np.asarray(rainfall, dtype=float)
    pet_arr = np.asarray(pet, dtype=float)
    flow = np.asarray(streamflow, dtype=float)
    rows = []
    targets = []
    for idx in range(history, len(flow)):
        rows.append(
            [
                rain[idx],
                pet_arr[idx],
                rain[idx - 1],
                pet_arr[idx - 1],
                flow[idx - 1],
                flow[idx - 2],
                flow[idx - 3],
            ]
        )
        targets.append(flow[idx])
    return np.asarray(rows, dtype=float), np.asarray(targets, dtype=float)


@dataclass
class SequenceArrays:
    features: np.ndarray
    targets: np.ndarray
    feature_mean: np.ndarray
    feature_std: np.ndarray
    target_mean: float
    target_std: float


def build_sequence_arrays(
    rainfall: list[float],
    pet: list[float],
    streamflow: list[float],
    sequence_length: int = 8,
) -> SequenceArrays:
    rain = np.asarray(rainfall, dtype=float)
    pet_arr = np.asarray(pet, dtype=float)
    flow = np.asarray(streamflow, dtype=float)
    sequences = []
    targets = []
    for idx in range(sequence_length, len(flow)):
        sequence = []
        for inner in range(idx - sequence_length, idx):
            prev_flow = flow[inner - 1] if inner > 0 else flow[0]
            sequence.append([rain[inner], pet_arr[inner], prev_flow])
        sequences.append(sequence)
        targets.append(flow[idx])
    seq_arr = np.asarray(sequences, dtype=np.float32)
    target_arr = np.asarray(targets, dtype=np.float32)
    feature_mean = seq_arr.mean(axis=(0, 1))
    feature_std = seq_arr.std(axis=(0, 1)) + 1e-6
    target_mean = float(target_arr.mean())
    target_std = float(target_arr.std() + 1e-6)
    return SequenceArrays(
        features=seq_arr,
        targets=target_arr,
        feature_mean=feature_mean,
        feature_std=feature_std,
        target_mean=target_mean,
        target_std=target_std,
    )


def _try_import_torch():
    try:
        import torch  # type: ignore
        from torch import nn  # type: ignore
        from torch.utils.data import DataLoader, TensorDataset  # type: ignore

        return torch, nn, DataLoader, TensorDataset
    except Exception:
        return None, None, None, None


def _build_lstm_regressor(input_size: int = 3, hidden_size: int = 24, num_layers: int = 1):
    torch, nn, _, _ = _try_import_torch()
    if torch is None or nn is None:
        return None

    class LSTMRegressor(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
            )
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):
            output, _ = self.lstm(x)
            last_state = output[:, -1, :]
            return self.head(last_state).squeeze(-1)

    return LSTMRegressor()


def train_forecast_model_bundle(
    dataset_path: str | Path,
    *,
    output_path: str | Path | None = None,
    max_rows: int = 12000,
    sequence_length: int = 8,
    lstm_epochs: int = 6,
    lstm_batch_size: int = 128,
    random_seed: int = 42,
) -> dict[str, Any]:
    np.random.seed(random_seed)

    dataset = load_basin_dataset(dataset_path)
    rainfall = dataset.rainfall[-max_rows:]
    pet = dataset.pet[-max_rows:]
    streamflow = dataset.streamflow[-max_rows:]

    X, y = build_tabular_features(rainfall, pet, streamflow)
    split_idx = max(int(len(y) * 0.8), 1)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    if len(X_val) == 0:
        X_train, X_val = X[:-1], X[-1:]
        y_train, y_val = y[:-1], y[-1:]

    linear_model = LinearRegression()
    linear_model.fit(X_train, y_train)
    linear_pred = linear_model.predict(X_val)

    rf_model = RandomForestRegressor(
        n_estimators=80,
        max_depth=12,
        min_samples_leaf=4,
        random_state=random_seed,
        n_jobs=int(os.environ.get("HUADONG_RF_N_JOBS", "1")),
    )
    rf_model.fit(X_train, y_train)
    rf_pred = rf_model.predict(X_val)

    seq = build_sequence_arrays(rainfall, pet, streamflow, sequence_length=sequence_length)
    seq_split = max(int(len(seq.targets) * 0.8), 1)
    train_features = seq.features[:seq_split]
    train_targets = seq.targets[:seq_split]
    val_features = seq.features[seq_split:]
    val_targets = seq.targets[seq_split:]
    if len(val_features) == 0:
        train_features, val_features = seq.features[:-1], seq.features[-1:]
        train_targets, val_targets = seq.targets[:-1], seq.targets[-1:]

    train_norm = (train_features - seq.feature_mean) / seq.feature_std
    val_norm = (val_features - seq.feature_mean) / seq.feature_std
    train_target_norm = (train_targets - seq.target_mean) / seq.target_std

    torch, nn, DataLoader, TensorDataset = _try_import_torch()
    lstm_asset: dict[str, Any]
    if torch is not None and nn is not None and DataLoader is not None and TensorDataset is not None:
        torch.manual_seed(random_seed)
        lstm_model = _build_lstm_regressor()
        assert lstm_model is not None
        optimizer = torch.optim.Adam(lstm_model.parameters(), lr=1e-3)
        loss_fn = nn.MSELoss()
        train_loader = DataLoader(
            TensorDataset(
                torch.tensor(train_norm, dtype=torch.float32),
                torch.tensor(train_target_norm, dtype=torch.float32),
            ),
            batch_size=lstm_batch_size,
            shuffle=True,
        )
        lstm_model.train()
        for _ in range(lstm_epochs):
            for batch_x, batch_y in train_loader:
                optimizer.zero_grad()
                pred = lstm_model(batch_x)
                loss = loss_fn(pred, batch_y)
                loss.backward()
                optimizer.step()

        lstm_model.eval()
        with torch.no_grad():
            val_pred_norm = lstm_model(torch.tensor(val_norm, dtype=torch.float32)).cpu().numpy()
        lstm_pred = val_pred_norm * seq.target_std + seq.target_mean
        lstm_asset = {
            "model_type": "torch_lstm_regressor",
            "feature_names": ["rain_t", "pet_t", "prev_flow"],
            "state_dict": lstm_model.state_dict(),
            "config": {
                "input_size": 3,
                "hidden_size": 24,
                "num_layers": 1,
                "sequence_length": sequence_length,
            },
            "normalization": {
                "feature_mean": seq.feature_mean.tolist(),
                "feature_std": seq.feature_std.tolist(),
                "target_mean": seq.target_mean,
                "target_std": seq.target_std,
            },
            "rmse": _rmse(lstm_pred, val_targets.astype(float)),
        }
    else:
        mlp_model = MLPRegressor(
            hidden_layer_sizes=(32, 16),
            max_iter=200,
            random_state=random_seed,
        )
        flat_train = train_norm.reshape(len(train_norm), -1)
        flat_val = val_norm.reshape(len(val_norm), -1)
        mlp_model.fit(flat_train, train_target_norm)
        val_pred_norm = mlp_model.predict(flat_val)
        lstm_pred = val_pred_norm * seq.target_std + seq.target_mean
        lstm_asset = {
            "model_type": "mlp_regressor_fallback",
            "feature_names": ["sequence_flattened"],
            "model": mlp_model,
            "config": {
                "sequence_length": sequence_length,
                "feature_size": 3,
            },
            "normalization": {
                "feature_mean": seq.feature_mean.tolist(),
                "feature_std": seq.feature_std.tolist(),
                "target_mean": seq.target_mean,
                "target_std": seq.target_std,
            },
            "rmse": _rmse(lstm_pred, val_targets.astype(float)),
        }

    bundle = {
        "metadata": {
            "bundle_version": 1,
            "training_dataset_path": str(Path(dataset_path).expanduser().resolve()),
            "n_rows_used": len(streamflow),
            "sequence_length": sequence_length,
            "random_seed": random_seed,
            "serializer": preferred_bundle_serializer(),
        },
        "hydrological": default_hydrological_assets(),
        "learned_models": {
            "linear": {
                "model_type": "linear_regression",
                "feature_names": list(FEATURE_NAMES),
                "model": linear_model,
                "rmse": _rmse(linear_pred, y_val),
            },
            "rf": {
                "model_type": "random_forest_regressor",
                "feature_names": list(FEATURE_NAMES),
                "model": rf_model,
                "rmse": _rmse(rf_pred, y_val),
            },
            "lstm": {
                **lstm_asset,
            },
            "ensemble_initial_weights": {
                "model_names": ["xaj", "gr4j", "rf", "lstm"],
                "weights": [0.1, 0.2, 0.5, 0.2],
            },
        },
    }
    bundle_path = save_model_asset_bundle(bundle, output_path)
    bundle["metadata"]["bundle_path"] = str(bundle_path)
    return bundle


def predict_with_rf_asset(
    model_asset: dict[str, Any] | None,
    rainfall: list[float],
    pet: list[float],
    observed: list[float],
) -> list[float] | None:
    if not model_asset or model_asset.get("model") is None:
        return None
    X, _ = build_tabular_features(rainfall, pet, observed)
    if len(X) == 0:
        return None
    model = model_asset["model"]
    pred = np.asarray(model.predict(X), dtype=float)
    prefix = observed[:3]
    return [float(value) for value in list(prefix) + pred.tolist()]


def predict_with_lstm_asset(
    model_asset: dict[str, Any] | None,
    rainfall: list[float],
    pet: list[float],
    observed: list[float],
) -> list[float] | None:
    if not model_asset:
        return None
    if model_asset.get("model") is not None:
        seq_len = int(model_asset.get("config", {}).get("sequence_length", 8))
        seq = build_sequence_arrays(rainfall, pet, observed, sequence_length=seq_len)
        if len(seq.features) == 0:
            return None
        normalization = model_asset.get("normalization", {})
        feature_mean = np.asarray(normalization["feature_mean"], dtype=np.float32)
        feature_std = np.asarray(normalization["feature_std"], dtype=np.float32)
        target_mean = float(normalization["target_mean"])
        target_std = float(normalization["target_std"])
        normalized = (seq.features - feature_mean) / feature_std
        flat = normalized.reshape(len(normalized), -1)
        pred_norm = np.asarray(model_asset["model"].predict(flat), dtype=float)
        pred = pred_norm * target_std + target_mean
        prefix = observed[:seq_len]
        return [float(value) for value in list(prefix) + pred.tolist()]
    state_dict = model_asset.get("state_dict")
    config = model_asset.get("config", {})
    normalization = model_asset.get("normalization", {})
    if state_dict is None or not normalization:
        return None
    torch, _, _, _ = _try_import_torch()
    if torch is None:
        return None
    sequence_length = int(config.get("sequence_length", 8))
    seq = build_sequence_arrays(rainfall, pet, observed, sequence_length=sequence_length)
    if len(seq.features) == 0:
        return None
    model = _build_lstm_regressor(
        input_size=int(config.get("input_size", 3)),
        hidden_size=int(config.get("hidden_size", 24)),
        num_layers=int(config.get("num_layers", 1)),
    )
    if model is None:
        return None
    model.load_state_dict(state_dict)
    model.eval()
    feature_mean = np.asarray(normalization["feature_mean"], dtype=np.float32)
    feature_std = np.asarray(normalization["feature_std"], dtype=np.float32)
    target_mean = float(normalization["target_mean"])
    target_std = float(normalization["target_std"])
    normalized = (seq.features - feature_mean) / feature_std
    with torch.no_grad():
        pred_norm = model(torch.tensor(normalized, dtype=torch.float32)).cpu().numpy()
    pred = pred_norm * target_std + target_mean
    prefix = observed[:sequence_length]
    return [float(value) for value in list(prefix) + pred.tolist()]
