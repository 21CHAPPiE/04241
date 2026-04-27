from __future__ import annotations

import csv
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.rest_api import create_app


def _write_subset_csv(source: Path, target: Path, rows: int) -> Path:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        assert fieldnames is not None
        selected = []
        for idx, row in enumerate(reader):
            if idx >= rows:
                break
            selected.append(dict(row))
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected)
    return target


def _poll_job(client: TestClient, job_id: str, timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for job {job_id}")


def test_rest_health_and_sync_chain(project_root: Path, tmp_path: Path) -> None:
    basin_small = _write_subset_csv(
        project_root / "data" / "basin_001_hourly.csv",
        tmp_path / "basin_small.csv",
        rows=96,
    )
    multi_small = _write_subset_csv(
        project_root / "data" / "rain_15stations_flow.csv",
        tmp_path / "multistation_small.csv",
        rows=96,
    )
    app = create_app(job_root=tmp_path / "jobs")
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["protocol"] == "rest"

    dataset_basin = client.post(
        "/dataset/profile",
        json={"dataset_path": str(basin_small), "output_root": str(tmp_path / "dataset-basin")},
    )
    assert dataset_basin.status_code == 200
    basin_payload = dataset_basin.json()
    assert Path(basin_payload["artifact_paths"]["dataset_profile"]).exists()

    dataset_multi = client.post(
        "/dataset/profile",
        json={
            "dataset_path": str(multi_small),
            "output_root": str(tmp_path / "dataset-multi"),
            "options": {"profile_type": "multistation"},
        },
    )
    assert dataset_multi.status_code == 200

    assets = client.post("/model-assets/profile", json={"output_root": str(tmp_path / "assets")})
    assert assets.status_code == 200

    train_bundle = client.post(
        "/train-model-bundle",
        json={
            "dataset_path": str(basin_small),
            "output_root": str(tmp_path / "train-bundle"),
            "options": {
                "max_rows": 96,
                "sequence_length": 4,
                "lstm_epochs": 1,
                "bundle_path": str(tmp_path / "train-bundle" / "bundle.pt"),
            },
        },
    )
    assert train_bundle.status_code == 200

    forecast = client.post(
        "/forecast",
        json={"dataset_path": str(basin_small), "output_root": str(tmp_path / "forecast")},
    )
    assert forecast.status_code == 200
    forecast_payload = forecast.json()
    forecast_csv = Path(forecast_payload["artifact_paths"]["forecast"])
    assert forecast_payload["status"] == "completed"
    assert forecast_csv.exists()

    analysis = client.post(
        "/analysis",
        json={
            "dataset_path": str(basin_small),
            "output_root": str(tmp_path / "analysis"),
            "options": {"column": "streamflow"},
        },
    )
    assert analysis.status_code == 200

    ensemble = client.post(
        "/ensemble",
        json={
            "file_path": str(forecast_csv),
            "output_root": str(tmp_path / "ensemble"),
            "options": {
                "method": "bma",
                "observation_dataset": str(basin_small),
                "observation_column": "streamflow",
            },
        },
    )
    assert ensemble.status_code == 200
    ensemble_csv = Path(ensemble.json()["artifact_paths"]["ensemble"])
    assert ensemble_csv.exists()

    correction = client.post(
        "/correction",
        json={
            "file_path": str(ensemble_csv),
            "output_root": str(tmp_path / "correction"),
            "options": {
                "observation_dataset": str(basin_small),
                "observation_column": "streamflow",
            },
        },
    )
    assert correction.status_code == 200
    corrected_csv = Path(correction.json()["artifact_paths"]["correction"])
    assert corrected_csv.exists()

    risk = client.post(
        "/risk",
        json={
            "file_path": str(corrected_csv),
            "output_root": str(tmp_path / "risk"),
            "options": {
                "thresholds": {"flood": 300.0, "severe": 500.0},
                "model_columns": ["corrected_forecast"],
            },
        },
    )
    assert risk.status_code == 200
    assert Path(risk.json()["artifact_paths"]["risk"]).exists()

    warning = client.post(
        "/warning",
        json={
            "file_path": str(corrected_csv),
            "output_root": str(tmp_path / "warning"),
            "options": {
                "forecast_column": "corrected_forecast",
                "warning_threshold": 300.0,
                "lead_time_hours": 24,
            },
        },
    )
    assert warning.status_code == 200
    assert Path(warning.json()["artifact_paths"]["warning"]).exists()


def test_rest_async_job_endpoints(project_root: Path, tmp_path: Path) -> None:
    basin_small = _write_subset_csv(
        project_root / "data" / "basin_001_hourly.csv",
        tmp_path / "basin_small.csv",
        rows=96,
    )
    client = TestClient(create_app(job_root=tmp_path / "jobs"))

    jobs = {
        "/training/jobs": "model",
        "/calibration/jobs": "calibration",
        "/hpo/jobs": "hpo",
        "/lifecycle-smoke/jobs": "model",
    }
    for route, expected_artifact in jobs.items():
        response = client.post(
            route,
            json={"dataset_path": str(basin_small), "output_root": str(tmp_path / route.strip("/").replace("/", "-"))},
        )
        assert response.status_code == 202
        job = _poll_job(client, response.json()["job_id"])
        assert job["status"] == "completed"
        assert expected_artifact in job["result"]["artifact_paths"]
