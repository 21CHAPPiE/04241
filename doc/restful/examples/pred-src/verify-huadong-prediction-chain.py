from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def find_workspace_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "UnifiedGateway").exists() and (parent / "HuadongCode").exists():
            return parent
    raise RuntimeError("Failed to locate workspace root from script path")


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    workspace_root = find_workspace_root()
    unified_gateway_root = workspace_root / "UnifiedGateway"
    if str(unified_gateway_root) not in sys.path:
        sys.path.insert(0, str(unified_gateway_root))

    from gateway.app import create_app

    config_path = Path(__file__).with_name("huadong-prediction-chain.config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    run_root = Path(config["output_root"])
    request_dir = run_root / "requests"
    response_dir = run_root / "responses"
    request_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(job_root=run_root / "jobs")
    client = TestClient(app)

    health = client.get("/huadong/health")
    health.raise_for_status()
    save_json(response_dir / "00-health.response.json", health.json())

    dataset_payload = {
        "dataset_path": config["dataset_path"],
        "output_root": str(run_root / "dataset"),
        "options": {},
    }
    save_json(request_dir / "01-dataset-profile.request.json", dataset_payload)
    dataset = client.post("/huadong/dataset/profile", json=dataset_payload)
    dataset.raise_for_status()
    dataset_json = dataset.json()
    save_json(response_dir / "01-dataset-profile.response.json", dataset_json)

    assets_payload = {
        "output_root": str(run_root / "assets"),
        "options": {},
    }
    save_json(request_dir / "02-model-assets-profile.request.json", assets_payload)
    assets = client.post("/huadong/model-assets/profile", json=assets_payload)
    assets.raise_for_status()
    assets_json = assets.json()
    save_json(response_dir / "02-model-assets-profile.response.json", assets_json)

    analysis_payload = {
        "dataset_path": config["dataset_path"],
        "output_root": str(run_root / "analysis"),
        "options": {"column": config["analysis_column"]},
    }
    save_json(request_dir / "03-analysis.request.json", analysis_payload)
    analysis = client.post("/huadong/analysis", json=analysis_payload)
    analysis.raise_for_status()
    analysis_json = analysis.json()
    save_json(response_dir / "03-analysis.response.json", analysis_json)

    forecast_payload = {
        "dataset_path": config["dataset_path"],
        "output_root": str(run_root / "forecast"),
        "options": {},
    }
    save_json(request_dir / "04-forecast.request.json", forecast_payload)
    forecast = client.post("/huadong/forecast", json=forecast_payload)
    forecast.raise_for_status()
    forecast_json = forecast.json()
    save_json(response_dir / "04-forecast.response.json", forecast_json)

    ensemble_payload = {
        "file_path": forecast_json["artifact_paths"]["forecast"],
        "output_root": str(run_root / "ensemble"),
        "options": {
            "method": config["ensemble_method"],
            "observation_dataset": config["observation_dataset"],
            "observation_column": config["observation_column"],
        },
    }
    save_json(request_dir / "05-ensemble.request.json", ensemble_payload)
    ensemble = client.post("/huadong/ensemble", json=ensemble_payload)
    ensemble.raise_for_status()
    ensemble_json = ensemble.json()
    save_json(response_dir / "05-ensemble.response.json", ensemble_json)

    correction_payload = {
        "file_path": ensemble_json["artifact_paths"]["ensemble"],
        "output_root": str(run_root / "correction"),
        "options": {
            "observation_dataset": config["observation_dataset"],
            "observation_column": config["observation_column"],
        },
    }
    save_json(request_dir / "06-correction.request.json", correction_payload)
    correction = client.post("/huadong/correction", json=correction_payload)
    correction.raise_for_status()
    correction_json = correction.json()
    save_json(response_dir / "06-correction.response.json", correction_json)

    risk_payload = {
        "file_path": correction_json["artifact_paths"]["correction"],
        "output_root": str(run_root / "risk"),
        "options": {
            "thresholds": config["risk_thresholds"],
            "model_columns": config["risk_model_columns"],
        },
    }
    save_json(request_dir / "07-risk.request.json", risk_payload)
    risk = client.post("/huadong/risk", json=risk_payload)
    risk.raise_for_status()
    risk_json = risk.json()
    save_json(response_dir / "07-risk.response.json", risk_json)

    warning_payload = {
        "file_path": correction_json["artifact_paths"]["correction"],
        "output_root": str(run_root / "warning"),
        "options": {
            "forecast_column": config["warning_forecast_column"],
            "warning_threshold": config["warning_threshold"],
            "lead_time_hours": config["warning_lead_time_hours"],
        },
    }
    save_json(request_dir / "08-warning.request.json", warning_payload)
    warning = client.post("/huadong/warning", json=warning_payload)
    warning.raise_for_status()
    warning_json = warning.json()
    save_json(response_dir / "08-warning.response.json", warning_json)

    summary = {
        "status": "completed",
        "forecast_csv": forecast_json["artifact_paths"]["forecast"],
        "ensemble_csv": ensemble_json["artifact_paths"]["ensemble"],
        "corrected_csv": correction_json["artifact_paths"]["correction"],
        "risk_json": risk_json["artifact_paths"]["risk"],
        "warning_json": warning_json["artifact_paths"]["warning"],
    }
    save_json(run_root / "pipeline-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
