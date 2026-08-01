import os

from arq import create_pool
from arq.connections import RedisSettings


def get_redis_settings() -> RedisSettings:
    host = os.environ.get("REDIS_HOST", "")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    return RedisSettings(host=host or "localhost", port=port)


def redis_available() -> bool:
    return bool(os.environ.get("REDIS_HOST"))


async def create_redis_pool():
    return await create_pool(get_redis_settings())


async def enqueue_ingest_job(user_id: int, fit_bytes: bytes, source: str, source_ref: str) -> str | None:
    """Enqueue an ingest job if Redis is available. Returns job_id or None if sync fallback needed."""
    if not redis_available():
        return None
    pool = await create_redis_pool()
    try:
        job = await pool.enqueue_job("ingest_job", user_id=user_id, fit_bytes=fit_bytes, source=source, source_ref=source_ref)
        return job.job_id
    finally:
        await pool.aclose()


async def get_job_status(job_id: str) -> dict:
    """Get the status of a job by ID. Returns status and result if complete."""
    if not redis_available():
        return {"status": "unknown", "result": None}
    pool = await create_redis_pool()
    try:
        from arq.jobs import Job
        job = Job(job_id, pool)
        job_status = await job.status()
        result = await job.result_info()
        
        status_map = {
            "deferred": "pending",
            "queued": "pending",
            "in_progress": "processing",
            "complete": "complete",
            "not_found": "not_found",
        }
        
        return {
            "status": status_map.get(str(job_status).split(".")[-1].lower(), "unknown"),
            "result": result.result if result else None,
        }
    finally:
        await pool.aclose()


async def enqueue_sync_xert_job(user_id: int) -> str | None:
    """Enqueue a Xert sync job for a user. Returns job_id or None if Redis not available."""
    if not redis_available():
        return None
    pool = await create_redis_pool()
    try:
        job = await pool.enqueue_job("sync_xert_job", user_id=user_id)
        return job.job_id
    finally:
        await pool.aclose()