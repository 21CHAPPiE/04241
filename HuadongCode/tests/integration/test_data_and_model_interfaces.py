from __future__ import annotations

from pathlib import Path

from app.core.data_loading import describe_dataset, load_basin_dataset, load_multistation_dataset
from app.core.model_assets import describe_model_asset_bundle, load_model_asset_bundle
from app.core.trained_models import train_forecast_model_bundle


def test_data_loading_interfaces_describe_checked_in_datasets(project_root: Path) -> None:
    basin = load_basin_dataset(project_root / "data" / "basin_001_hourly.csv")
    multistation = load_multistation_dataset(project_root / "data" / "rain_15stations_flow.csv")

    basin_desc = describe_dataset(basin)
    multi_desc = describe_dataset(multistation)

    assert basin_desc["schema_name"] == "basin_hourly"
    assert basin_desc["n_rows"] > 1000
    assert basin_desc["time_start"] is not None

    assert multi_desc["schema_name"] == "multistation_hourly"
    assert multi_desc["n_stations"] >= 10
    assert multi_desc["n_rows"] > 1000


def test_training_bundle_saves_with_hydrological_and_learned_assets(
    project_root: Path,
    tmp_path: Path,
) -> None:
    bundle_path = tmp_path / "forecast_model_bundle.pt"
    bundle = train_forecast_model_bundle(
        project_root / "data" / "basin_001_hourly.csv",
        output_path=bundle_path,
        max_rows=2000,
        lstm_epochs=1,
    )
    assert bundle_path.exists()

    loaded = load_model_asset_bundle(bundle_path)
    description = describe_model_asset_bundle(loaded)

    assert description["metadata"]["bundle_available"] is True
    assert "xaj" in description["hydrological_models"]
    assert "gr4j" in description["hydrological_models"]
    assert "rf" in description["learned_models"]
    assert "lstm" in description["learned_models"]
    assert bundle["learned_models"]["rf"]["rmse"] >= 0.0
