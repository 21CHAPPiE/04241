from __future__ import annotations

import csv
import time
from pathlib import Path

from fastapi.testclient import TestClient

from gateway.app import create_app


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


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


def _event_path(case_id: str) -> str:
    repo = WORKSPACE_ROOT / "TanKengCode"
    if case_id == "6.4.1":
        return str(repo / "data" / "flood_event" / "2024072617.csv")
    if case_id == "6.4.2":
        return str(repo / "data" / "flood_event" / "2024061623.csv")
    if case_id == "6.4.3":
        return str(repo / "data" / "2024072617_with_pred.csv")
    return str(repo / "data" / "flood_event" / "2024061623.csv")


def _poll_job(client: TestClient, path: str, timeout_s: float = 30.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for job at {path}")


def test_gateway_health_and_mounted_sync_routes(tmp_path: Path) -> None:
    basin_small = _write_subset_csv(
        WORKSPACE_ROOT / "HuadongCode" / "data" / "basin_001_hourly.csv",
        tmp_path / "basin_small.csv",
        rows=96,
    )

    client = TestClient(create_app(job_root=tmp_path / "jobs"))

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["available_services"] == ["huadong", "tanken"]

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["route_prefixes"]["huadong"] == "/huadong"

    huadong_health = client.get("/huadong/health")
    assert huadong_health.status_code == 200
    assert huadong_health.json()["service"] == "huadong-rest"

    tanken_health = client.get("/tanken/health")
    assert tanken_health.status_code == 200
    assert tanken_health.json()["service"] == "tanken-rest"

    huadong_dataset = client.post(
        "/huadong/dataset/profile",
        json={"dataset_path": str(basin_small), "output_root": str(tmp_path / "huadong-dataset")},
    )
    assert huadong_dataset.status_code == 200
    assert Path(huadong_dataset.json()["artifact_paths"]["dataset_profile"]).exists()

    tanken_cases = client.get("/tanken/cases")
    assert tanken_cases.status_code == 200
    assert tanken_cases.json()["count"] == 4

    tanken_status = client.post(
        "/tanken/cases/6.4.1/status",
        json={"event_csv_path": _event_path("6.4.1")},
    )
    assert tanken_status.status_code == 200
    assert tanken_status.json()["scenario_id"] == "6.4.1"


def test_gateway_mounted_async_routes(tmp_path: Path) -> None:
    basin_small = _write_subset_csv(
        WORKSPACE_ROOT / "HuadongCode" / "data" / "basin_001_hourly.csv",
        tmp_path / "basin_small.csv",
        rows=96,
    )
    client = TestClient(create_app(job_root=tmp_path / "jobs"))

    huadong_job = client.post(
        "/huadong/training/jobs",
        json={"dataset_path": str(basin_small), "output_root": str(tmp_path / "huadong-training")},
    )
    assert huadong_job.status_code == 202
    huadong_result = _poll_job(client, f"/huadong/jobs/{huadong_job.json()['job_id']}")
    assert huadong_result["status"] == "completed"
    assert "model" in huadong_result["result"]["artifact_paths"]

    tanken_job = client.post(
        "/tanken/cases/6.4.2/run-jobs",
        json={"event_csv_path": _event_path("6.4.2"), "persist_result": False},
    )
    assert tanken_job.status_code == 202
    tanken_result = _poll_job(client, f"/tanken/jobs/{tanken_job.json()['job_id']}")
    assert tanken_result["status"] == "completed"
    assert tanken_result["result"]["decision_summary"]["recommended_plan"].startswith("Plan ")
