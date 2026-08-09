"""
Job enqueue functions for TrainingDash.

This module provides functions to enqueue background jobs via SAQ.
Jobs are processed by the worker defined in worker.py.

Note: SAQ with Postgres uses JSON serialization, so binary data must be
base64-encoded before enqueueing.
"""

import base64

from trainingdash.queue import get_queue, queue_available


async def enqueue_ingest_job(user_id: int, fit_bytes: bytes, source: str, source_ref: str) -> str | None:
    """Enqueue an ingest job if queue is available. Returns job key or None if sync fallback needed."""
    if not queue_available():
        return None
    queue = await get_queue()
    # Base64 encode bytes for JSON serialization
    fit_bytes_b64 = base64.b64encode(fit_bytes).decode('ascii')
    job = await queue.enqueue("ingest_job", user_id=user_id, fit_bytes_b64=fit_bytes_b64, source=source, source_ref=source_ref)
    return job.key if job else None


async def get_job_status(job_key: str) -> dict:
    """Get the status of a job by key. Returns status and result if complete."""
    if not queue_available():
        return {"status": "unknown", "result": None}
    
    queue = await get_queue()
    job = await queue.job(job_key)
    
    if job is None:
        return {"status": "not_found", "result": None}
    
    # Map SAQ status to our API status
    status_map = {
        "new": "pending",
        "deferred": "pending",
        "queued": "pending",
        "active": "processing",
        "complete": "complete",
        "failed": "failed",
        "aborted": "aborted",
        "aborting": "processing",
    }
    
    return {
        "status": status_map.get(job.status, "unknown"),
        "result": job.result,
    }


async def enqueue_sync_xert_job(user_id: int) -> str | None:
    """Enqueue a Xert sync job for a user. Returns job key or None if queue not available."""
    if not queue_available():
        return None
    queue = await get_queue()
    job = await queue.enqueue("sync_xert_job", user_id=user_id)
    return job.key if job else None


async def enqueue_sync_garmin_job(user_id: int) -> str | None:
    """Enqueue a Garmin sync job for a user. Returns job key or None if queue not available."""
    if not queue_available():
        return None
    queue = await get_queue()
    job = await queue.enqueue("sync_garmin_job", user_id=user_id)
    return job.key if job else None


async def enqueue_recalculate_after_delete_job(user_id: int) -> str | None:
    """
    Enqueue fitness/breakthrough recalculation after an activity is deleted.

    Returns job key or None if queue is not available (recalculation is skipped
    in that case — acceptable for development environments).
    """
    if not queue_available():
        return None
    queue = await get_queue()
    job = await queue.enqueue("recalculate_after_delete_job", user_id=user_id)
    return job.key if job else None


async def enqueue_recalculate_metrics_job(user_id: int) -> str | None:
    """
    Enqueue a metric recalculation job for a user.

    Recomputes NP, IF, TSS, W'bal, and zone times for all activities with
    power data. Updates the RecalculationJob row with live status.

    Returns job key or None if queue is not available.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    job = await queue.enqueue("recalculate_metrics_job", user_id=user_id)
    return job.key if job else None
