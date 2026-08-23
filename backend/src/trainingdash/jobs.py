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
    fit_bytes_b64 = base64.b64encode(fit_bytes).decode("ascii")
    # Ingest needs longer timeout than SAQ default (10s) due to geocoding rate limits
    # (1 req/sec) and potential network latency
    job = await queue.enqueue(
        "ingest_job", user_id=user_id, fit_bytes_b64=fit_bytes_b64, source=source, source_ref=source_ref, timeout=60
    )
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


async def enqueue_sync_xert_job(user_id: int, scheduled: float | None = None) -> str | None:
    """Enqueue a Xert sync job for a user. Returns job key or None if queue not available.

    Pass ``scheduled`` (unix seconds) to defer the job.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Sync jobs need longer timeout for external API calls and FIT file processing
    # Only pass scheduled if explicitly set (None would cause NOT NULL violation)
    kwargs = {"user_id": user_id, "timeout": 300}
    if scheduled is not None:
        kwargs["scheduled"] = scheduled
    job = await queue.enqueue("sync_xert_job", **kwargs)
    return job.key if job else None


async def enqueue_sync_garmin_job(user_id: int, scheduled: float | None = None) -> str | None:
    """Enqueue a Garmin sync job for a user. Returns job key or None if queue not available.

    Pass ``scheduled`` (unix seconds) to defer the job.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Sync jobs need longer timeout for external API calls and FIT file processing
    # Only pass scheduled if explicitly set (None would cause NOT NULL violation)
    kwargs = {"user_id": user_id, "timeout": 300}
    if scheduled is not None:
        kwargs["scheduled"] = scheduled
    job = await queue.enqueue("sync_garmin_job", **kwargs)
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
    # Recalculation may process many activities; give it longer timeout
    job = await queue.enqueue("recalculate_metrics_job", user_id=user_id, timeout=300)
    return job.key if job else None


async def enqueue_match_route_job(activity_id: str, user_id: int) -> str | None:
    """Enqueue route matching for a freshly-ingested activity. Returns job key or None if queue not available."""
    if not queue_available():
        return None
    queue = await get_queue()
    job = await queue.enqueue("match_route_job", activity_id=activity_id, user_id=user_id)
    return job.key if job else None



async def enqueue_fetch_weather_job(user_id: int, activity_id: str | None = None) -> str | None:
    """
    Enqueue a weather fetch job for activities pending weather data.

    If activity_id is provided, fetches weather for that single activity.
    Otherwise, processes pending activities for the user.

    Returns job key or None if queue is not available.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    kwargs = {"user_id": user_id, "timeout": 120}
    if activity_id:
        kwargs["activity_id"] = activity_id
    job = await queue.enqueue("fetch_weather_job", **kwargs)
    return job.key if job else None


async def enqueue_batch_weather_job(user_id: int, throttle_seconds: float = 1.0) -> str | None:
    """
    Enqueue a batch weather fetch job for all pending activities.

    This job processes all activities with pending weather status using
    throttling to avoid API rate limits. Designed for use after bulk imports.

    Args:
        user_id: User to process activities for
        throttle_seconds: Delay between API calls (default 1.0s)

    Returns:
        Job key or None if queue is not available
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Batch weather can take a long time for many activities
    # 1000 activities × 3 hours avg × 1s throttle = ~50 minutes
    job = await queue.enqueue(
        "batch_weather_job",
        user_id=user_id,
        throttle_seconds=throttle_seconds,
        timeout=7200,  # 2 hour timeout
    )
    return job.key if job else None


async def enqueue_backup_job() -> str | None:
    """
    Enqueue a backup job to run on the worker.

    Backups must run on the worker container because it has the /data/backups
    volume mounted. The use case handles all logic including history entry
    creation, restic operations, and retention policy.

    Returns job key or None if queue is not available.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Backups can be slow depending on data size; give generous timeout
    job = await queue.enqueue("backup_job", timeout=1800)
    return job.key if job else None
