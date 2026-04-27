"""REST API facade over Tanken MCP-style tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .tanken_config import get_tanken_case
from .tanken_mcp_tools import setup_tanken_mcp_tools
from .tanken_rest_jobs import LocalJobStore


class _FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class CaseContextRequest(BaseModel):
    event_csv_path: str | None = None
    reservoir_config_path: str | None = None


class OptimizeRequest(CaseContextRequest):
    horizon_hours: int = 0
    requested_module_type: str = ""
    min_flow: float = 50.0
    max_flow: float = 0.0
    control_interval_seconds: int = 0


class SimulationRequest(CaseContextRequest):
    target_outflow: float
    module_type: str = "constant_release"
    module_parameters: dict[str, Any] = Field(default_factory=dict)


class EvaluationRequest(SimulationRequest):
    eco_min_flow: float = 50.0


class RunCaseJobRequest(CaseContextRequest):
    persist_result: bool = False


class RunAllCasesJobRequest(BaseModel):
    reservoir_config_path: str | None = None
    persist_result: bool = False


def create_app(*, job_root: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Tanken REST API", version="0.1.0")
    jobs = LocalJobStore(job_root)
    tools = _build_tools()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "tanken-rest",
            "protocol": "rest",
            "mcp_compatibility": "preserved",
        }

    @app.get("/cases")
    def list_cases() -> dict[str, Any]:
        return tools["list_tanken_cases"]()

    @app.get("/cases/{case_id}")
    def describe_case(case_id: str) -> dict[str, Any]:
        _require_case(case_id)
        return tools["describe_tanken_case"](case_id)

    @app.post("/cases/{case_id}/status")
    def case_status(case_id: str, request: CaseContextRequest) -> dict[str, Any]:
        _require_case(case_id)
        return _run_sync(
            lambda: tools["get_tanken_case_status"](
                case_id,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
            )
        )

    @app.post("/cases/{case_id}/rules")
    def case_rules(case_id: str, request: CaseContextRequest) -> dict[str, Any]:
        _require_case(case_id)
        return _run_sync(
            lambda: tools["query_tanken_dispatch_rules"](
                case_id,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
            )
        )

    @app.post("/cases/{case_id}/optimize")
    def case_optimize(case_id: str, request: OptimizeRequest) -> dict[str, Any]:
        _require_case(case_id)
        return _run_sync(
            lambda: tools["optimize_tanken_release_plan"](
                case_id,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
                horizon_hours=request.horizon_hours,
                requested_module_type=request.requested_module_type,
                min_flow=request.min_flow,
                max_flow=request.max_flow,
                control_interval_seconds=request.control_interval_seconds,
            )
        )

    @app.post("/cases/{case_id}/simulate")
    def case_simulate(case_id: str, request: SimulationRequest) -> dict[str, Any]:
        _require_case(case_id)
        return _run_sync(
            lambda: tools["simulate_tanken_dispatch_program"](
                case_id,
                target_outflow=request.target_outflow,
                module_type=request.module_type,
                module_parameters=request.module_parameters,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
            )
        )

    @app.post("/cases/{case_id}/evaluate")
    def case_evaluate(case_id: str, request: EvaluationRequest) -> dict[str, Any]:
        _require_case(case_id)
        return _run_sync(
            lambda: tools["evaluate_tanken_dispatch_result"](
                case_id,
                target_outflow=request.target_outflow,
                module_type=request.module_type,
                module_parameters=request.module_parameters,
                eco_min_flow=request.eco_min_flow,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
            )
        )

    @app.post("/cases/{case_id}/run-jobs", status_code=202)
    def run_case_job(case_id: str, request: RunCaseJobRequest) -> JSONResponse:
        _require_case(case_id)
        return _submit_job(
            jobs,
            operation=f"run-case:{case_id}",
            input_payload={"case_id": case_id, **request.model_dump(mode="json")},
            runner=lambda: tools["run_tanken_case"](
                case_id,
                event_csv_path=request.event_csv_path,
                reservoir_config_path=request.reservoir_config_path,
                persist_result=request.persist_result,
            ),
        )

    @app.post("/cases/run-all-jobs", status_code=202)
    def run_all_cases_job(request: RunAllCasesJobRequest) -> JSONResponse:
        return _submit_job(
            jobs,
            operation="run-all-cases",
            input_payload=request.model_dump(mode="json"),
            runner=lambda: tools["run_all_tanken_cases"](
                reservoir_config_path=request.reservoir_config_path,
                persist_result=request.persist_result,
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


def _build_tools() -> dict[str, Any]:
    mcp = _FakeMCP()
    setup_tanken_mcp_tools(mcp)
    return mcp.tools


def _require_case(case_id: str) -> None:
    try:
        get_tanken_case(case_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "case_not_found", "message": f"Unknown case_id: {case_id}"},
        ) from exc


def _run_sync(runner) -> dict[str, Any]:
    try:
        return runner()
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
