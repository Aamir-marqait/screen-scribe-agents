"""In-process async job tracker.

Used by the script analyzer to support the n8n contract:
  POST /analyze  ->  { jobId }
  GET  /analyze/status/{jobId}  ->  { status, result | error }

This is process-local and not durable across restarts. When we add Redis
for the worker service, swap this implementation for a Redis-backed one
behind the same interface. Until then, single-instance deployment is fine
(Railway's default).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Awaitable, Callable, Literal

JobStatus = Literal["pending", "running", "completed", "error"]


@dataclass
class Job:
    id: str
    status: JobStatus = "pending"
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None


_JOBS: dict[str, Job] = {}
_JOBS_LOCK = Lock()
JOB_TTL_SECONDS = 60 * 60  # finished jobs are kept for 1 hour


def _purge_expired() -> None:
    now = time.time()
    with _JOBS_LOCK:
        stale = [
            jid
            for jid, job in _JOBS.items()
            if job.finished_at is not None and (now - job.finished_at) > JOB_TTL_SECONDS
        ]
        for jid in stale:
            _JOBS.pop(jid, None)


def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    _purge_expired()
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def _set(job_id: str, **fields: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)


def run_in_background(job_id: str, coro_factory: Callable[[], Awaitable[Any]]) -> None:
    """Schedule ``coro_factory()`` to run on the running event loop, updating
    the job state as it progresses.
    """

    async def runner() -> None:
        _set(job_id, status="running")
        try:
            result = await coro_factory()
            _set(job_id, status="completed", result=result, finished_at=time.time())
        except Exception as exc:  # noqa: BLE001 — we want to capture any failure
            _set(job_id, status="error", error=str(exc), finished_at=time.time())

    asyncio.create_task(runner())
