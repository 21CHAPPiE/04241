from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
HUADONG_ROOT = WORKSPACE_ROOT / "HuadongCode"
TANKEN_ROOT = WORKSPACE_ROOT / "TanKengCode"


def _ensure_project_import_paths() -> None:
    for root in (str(HUADONG_ROOT), str(TANKEN_ROOT)):
        if root in sys.path:
            sys.path.remove(root)
        sys.path.insert(0, root)


def create_app(*, job_root: str | Path | None = None) -> FastAPI:
    _ensure_project_import_paths()

    from app.rest_api import create_app as create_huadong_app
    from project.tanken_rest_api import create_app as create_tanken_app

    root = None if job_root is None else Path(job_root)
    huadong_job_root = None if root is None else root / "huadong"
    tanken_job_root = None if root is None else root / "tanken"

    app = FastAPI(title="Unified REST Gateway", version="0.1.0")

    @app.get("/")
    def index() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "unified-rest",
            "available_services": ["huadong", "tanken"],
            "route_prefixes": {
                "huadong": "/huadong",
                "tanken": "/tanken",
            },
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "unified-rest",
            "available_services": ["huadong", "tanken"],
            "route_prefixes": {
                "huadong": "/huadong",
                "tanken": "/tanken",
            },
        }

    app.mount("/huadong", create_huadong_app(job_root=huadong_job_root))
    app.mount("/tanken", create_tanken_app(job_root=tanken_job_root))
    return app
