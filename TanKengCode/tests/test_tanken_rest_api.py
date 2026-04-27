from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from project.tanken_rest_api import create_app


REPO_ROOT = Path(__file__).resolve().parents[1]


def _event_path(case_id: str) -> str:
    if case_id == "6.4.1":
        return str(REPO_ROOT / "data" / "flood_event" / "2024072617.csv")
    if case_id == "6.4.2":
        return str(REPO_ROOT / "data" / "flood_event" / "2024061623.csv")
    if case_id == "6.4.3":
        return str(REPO_ROOT / "data" / "2024072617_with_pred.csv")
    return str(REPO_ROOT / "data" / "flood_event" / "2024061623.csv")


def _poll_job(client: TestClient, job_id: str, timeout_s: float = 20.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for job {job_id}")


def test_tanken_rest_sync_routes(tmp_path: Path) -> None:
    client = TestClient(create_app(job_root=tmp_path / "jobs"))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["protocol"] == "rest"

    cases = client.get("/cases")
    assert cases.status_code == 200
    assert cases.json()["count"] == 4

    describe = client.get("/cases/6.4.3")
    assert describe.status_code == 200
    assert describe.json()["prediction_column"] == "predict"

    context_payload = {"event_csv_path": _event_path("6.4.1")}
    status = client.post("/cases/6.4.1/status", json=context_payload)
    assert status.status_code == 200
    assert status.json()["scenario_id"] == "6.4.1"

    rules = client.post("/cases/6.4.1/rules", json=context_payload)
    assert rules.status_code == 200
    assert rules.json()["target_level_m"] == 156.5

    optimize = client.post("/cases/6.4.1/optimize", json=context_payload)
    assert optimize.status_code == 200
    optimization = optimize.json()
    assert optimization["selected_module_type"]

    simulate = client.post(
        "/cases/6.4.1/simulate",
        json={
            **context_payload,
            "target_outflow": float(optimization["avg_release_m3s"]),
            "module_type": optimization["selected_module_type"],
            "module_parameters": optimization["selected_module_parameters"],
        },
    )
    assert simulate.status_code == 200
    assert simulate.json()["module_type"] == optimization["selected_module_type"]

    evaluate = client.post(
        "/cases/6.4.1/evaluate",
        json={
            **context_payload,
            "target_outflow": float(optimization["avg_release_m3s"]),
            "module_type": optimization["selected_module_type"],
            "module_parameters": optimization["selected_module_parameters"],
        },
    )
    assert evaluate.status_code == 200
    assert evaluate.json()["overall_score"] >= 0


def test_tanken_rest_async_routes(tmp_path: Path) -> None:
    client = TestClient(create_app(job_root=tmp_path / "jobs"))

    run_case = client.post(
        "/cases/6.4.2/run-jobs",
        json={"event_csv_path": _event_path("6.4.2"), "persist_result": False},
    )
    assert run_case.status_code == 202
    case_job = _poll_job(client, run_case.json()["job_id"])
    assert case_job["status"] == "completed"
    assert case_job["result"]["decision_summary"]["recommended_plan"].startswith("Plan ")

    run_all = client.post("/cases/run-all-jobs", json={"persist_result": False})
    assert run_all.status_code == 202
    all_job = _poll_job(client, run_all.json()["job_id"])
    assert all_job["status"] == "completed"
    assert sorted(all_job["result"].keys()) == ["6.4.1", "6.4.2", "6.4.3", "6.4.4"]
