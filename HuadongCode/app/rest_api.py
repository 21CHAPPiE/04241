"""REST API facade over the existing path-based tool layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.rest_jobs import LocalJobStore
from app.tools import (
    run_calibration_from_paths,
    run_data_analysis_from_paths,
    run_dataset_profile_from_paths,
    run_correction_from_paths,
    run_ensemble_from_paths,
    run_forecast_from_paths,
    run_hpo_from_paths,
    run_lifecycle_smoke_from_paths,
    run_model_asset_profile,
    run_risk_from_paths,
    run_train_model_bundle_from_paths,
    run_training_from_paths,
    run_warning_from_paths,
)


class PathToolRequest(BaseModel):
    dataset_path: str | None = None
    file_path: str | None = None
    output_root: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class OutputOptionsRequest(BaseModel):
    output_root: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


def create_app(*, job_root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Huadong Hydro REST API", version="0.1.0")
    jobs = LocalJobStore(job_root)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "huadong-rest",
            "protocol": "rest",
            "mcp_compatibility": "preserved",
        }

    @app.post("/dataset/profile")
    def dataset_profile(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_dataset_profile_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/model-assets/profile")
    def model_assets_profile(request: OutputOptionsRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_model_asset_profile(
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/train-model-bundle")
    def train_model_bundle(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_train_model_bundle_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/forecast")
    def forecast(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_forecast_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/analysis")
    def analysis(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_data_analysis_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/ensemble")
    def ensemble(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_ensemble_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/correction")
    def correction(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_correction_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/risk")
    def risk(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_risk_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/warning")
    def warning(request: PathToolRequest) -> dict[str, Any]:
        return _run_sync(
            lambda: run_warning_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            )
        )

    @app.post("/training/jobs", status_code=202)
    def training_job(request: PathToolRequest) -> JSONResponse:
        return _submit_job(
            jobs,
            operation="training",
            input_payload=request.model_dump(mode="json"),
            runner=lambda: run_training_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            ),
        )

    @app.post("/calibration/jobs", status_code=202)
    def calibration_job(request: PathToolRequest) -> JSONResponse:
        return _submit_job(
            jobs,
            operation="calibration",
            input_payload=request.model_dump(mode="json"),
            runner=lambda: run_calibration_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            ),
        )

    @app.post("/hpo/jobs", status_code=202)
    def hpo_job(request: PathToolRequest) -> JSONResponse:
        return _submit_job(
            jobs,
            operation="hpo",
            input_payload=request.model_dump(mode="json"),
            runner=lambda: run_hpo_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            ),
        )

    @app.post("/lifecycle-smoke/jobs", status_code=202)
    def lifecycle_smoke_job(request: PathToolRequest) -> JSONResponse:
        return _submit_job(
            jobs,
            operation="lifecycle-smoke",
            input_payload=request.model_dump(mode="json"),
            runner=lambda: run_lifecycle_smoke_from_paths(
                dataset_path=request.dataset_path,
                file_path=request.file_path,
                output_root=request.output_root,
                options=request.options,
            ),
        )

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        payload = jobs.read(job_id)
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error_code": "job_not_found",
                    "message": f"Unknown job_id: {job_id}",
                },
            )
        return payload

    return app


def _run_sync(runner) -> dict[str, Any]:
    try:
        return runner()
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "not_found", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_request", "message": str(exc)},
        ) from exc


def _submit_job(
    jobs: LocalJobStore,
    *,
    operation: str,
    input_payload: dict[str, Any],
    runner,
) -> JSONResponse:
    try:
        job = jobs.submit(operation=operation, input_payload=input_payload, runner=runner)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "invalid_request", "message": str(exc)},
        ) from exc
    return JSONResponse(status_code=202, content=job)
