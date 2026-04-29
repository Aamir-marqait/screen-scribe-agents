import asyncio

import pytest

from app.services.jobs import create_job, get_job, run_in_background


@pytest.mark.asyncio
async def test_job_lifecycle_completes():
    job = create_job()
    assert job.status == "pending"

    async def work() -> str:
        await asyncio.sleep(0.01)
        return "ok"

    run_in_background(job.id, work)
    # let the task run
    for _ in range(50):
        if get_job(job.id).status in {"completed", "error"}:
            break
        await asyncio.sleep(0.01)

    assert get_job(job.id).status == "completed"
    assert get_job(job.id).result == "ok"


@pytest.mark.asyncio
async def test_job_lifecycle_records_errors():
    job = create_job()

    async def boom() -> str:
        raise RuntimeError("nope")

    run_in_background(job.id, boom)
    for _ in range(50):
        if get_job(job.id).status in {"completed", "error"}:
            break
        await asyncio.sleep(0.01)

    final = get_job(job.id)
    assert final.status == "error"
    assert final.error == "nope"
