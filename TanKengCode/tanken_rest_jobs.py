"""Lightweight local job execution for Tanken REST endpoints."""

from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from fastapi.encoders import jsonable_encoder


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_JOB_ROOT = REPO_ROOT / "results" / "rest-jobs"


class LocalJobStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_JOB_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def submit(
        self,
        *,
        operation: str,
        input_payload: dict[str, Any],
        runner: Callable[[], Any],
    ) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        job = {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": self._timestamp(),
            "started_at": None,
            "completed_at": None,
            "operation": operation,
            "input": jsonable_encoder(input_payload),
            "result": None,
            "error": None,
        }
        self._write(job)
        thread = threading.Thread(target=self._run_job, args=(job_id, runner), daemon=True)
        thread.start()
        return job

    def read(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            path = self._job_path(job_id)
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

    def _run_job(self, job_id: str, runner: Callable[[], Any]) -> None:
        self._update(job_id, status="running", started_at=self._timestamp())
        try:
            result = jsonable_encoder(runner())
        except Exception as exc:  # pragma: no cover - exercised in integration-style tests
            self._update(
                job_id,
                status="failed",
                completed_at=self._timestamp(),
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            return
        self._update(
            job_id,
            status="completed",
            completed_at=self._timestamp(),
            result=result,
        )

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            payload = self.read(job_id)
            if payload is None:
                raise FileNotFoundError(f"Unknown job_id: {job_id}")
            payload.update(jsonable_encoder(fields))
            self._write(payload)

    def _write(self, payload: dict[str, Any]) -> None:
        path = self._job_path(payload["job_id"])
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    def _job_path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(tz=UTC).isoformat()
