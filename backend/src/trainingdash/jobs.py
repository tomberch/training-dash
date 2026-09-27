"""
Job enqueue functions for TrainingDash.

This module provides functions to enqueue background jobs via SAQ.
Jobs are processed by the worker defined in worker.py.

Note: SAQ with Postgres uses JSON serialization, so binary data must be
base64-encoded before enqueueing.
"""

import base64
import logging

from trainingdash.queue import get_queue, queue_available

logger = logging.getLogger(__name__)


class EnqueueError(Exception):
    """Raised when enqueueing a job fails for a real reason (queue unreachable, serialization).

    Distinct from the ``None`` return, which is the dev/no-queue signal
    (``queue_available()`` false — never fires in production).
    See ADR 0006 (decision 3) for the call-site policy.
    """


# Default retry policy for regular jobs (ADR 0006, decision 1).
DEFAULT_RETRIES = 3
DEFAULT_RETRY_DELAY = 30
DEFAULT_RETRY_BACKOFF = 300


async def _enqueue(queue, function: str, **kwargs):
    """Enqueue with the default retry policy; wrap failures in EnqueueError.

    Awaits SAQ's async enqueue. Returns the SAQ job or raises EnqueueError.
    """
    kwargs.setdefault("retries", DEFAULT_RETRIES)
    kwargs.setdefault("retry_delay", DEFAULT_RETRY_DELAY)
    kwargs.setdefault("retry_backoff", DEFAULT_RETRY_BACKOFF)
    try:
        return await queue.enqueue(function, **kwargs)
    except Exception as exc:
        raise EnqueueError(f"Failed to enqueue {function}: {exc}") from exc


async def touch_heartbeat(ctx: dict) -> None:
    """Refresh the current job's heartbeat (ADR 0006, decision 2).

    Long jobs call this between steps so SAQ's sweeper can tell a live job
    from a crashed one. Never raises: a heartbeat refresh failure must not
    kill a running job.
    """
    job = ctx.get("job") if isinstance(ctx, dict) else None
    if job is None:
        return
    update = getattr(job, "update", None)
    if update is None:
        return
    try:
        await update()
    except Exception:
        logger.exception("Heartbeat refresh failed for job %s", getattr(job, "key", "?"))


async def enqueue_ingest_job(user_id: int, fit_bytes: bytes, source: str, source_ref: str) -> str | None:
    """Enqueue an ingest job if queue is available. Returns job key or None if sync fallback needed."""
    if not queue_available():
        return None
    queue = await get_queue()
    # Base64 encode bytes for JSON serialization
    fit_bytes_b64 = base64.b64encode(fit_bytes).decode("ascii")
    # Large FIT files + 1 req/s geocoding rate limits (ADR 0006, decision 4)
    job = await _enqueue(
        queue,
        "ingest_job",
        user_id=user_id,
        fit_bytes_b64=fit_bytes_b64,
        source=source,
        source_ref=source_ref,
        timeout=300,
        heartbeat=120,
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


async def enqueue_import_xert_job(user_id: int, scheduled: float | None = None, key: str | None = None) -> str | None:
    """Enqueue a Xert import job for a user. Returns job key or None if queue not available.

    Pass ``scheduled`` (unix seconds) to defer the job.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Import jobs need longer timeout for external API calls and FIT file processing
    # Only pass scheduled if explicitly set (None would cause NOT NULL violation)
    kwargs = {"user_id": user_id, "timeout": 300}
    if scheduled is not None:
        kwargs["scheduled"] = scheduled
    if key is not None:
        kwargs["key"] = key
    kwargs.setdefault("heartbeat", 120)
    job = await _enqueue(queue, "import_xert_job", **kwargs)
    return job.key if job else None


async def enqueue_import_garmin_job(user_id: int, scheduled: float | None = None, key: str | None = None) -> str | None:
    """Enqueue a Garmin import job for a user. Returns job key or None if queue not available.

    Pass ``scheduled`` (unix seconds) to defer the job.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Import jobs need longer timeout for external API calls and FIT file processing
    # Only pass scheduled if explicitly set (None would cause NOT NULL violation)
    kwargs = {"user_id": user_id, "timeout": 300}
    if scheduled is not None:
        kwargs["scheduled"] = scheduled
    if key is not None:
        kwargs["key"] = key
    kwargs.setdefault("heartbeat", 120)
    job = await _enqueue(queue, "import_garmin_job", **kwargs)
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
    job = await _enqueue(queue, "recalculate_after_delete_job", user_id=user_id)
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
    job = await _enqueue(queue, "recalculate_metrics_job", user_id=user_id, timeout=300)
    return job.key if job else None


async def enqueue_match_route_job(activity_id: str, user_id: int) -> str | None:
    """Enqueue route matching for a freshly-ingested activity. Returns job key or None if queue not available."""
    if not queue_available():
        return None
    queue = await get_queue()
    # Explicit timeout — SAQ default is 10s, too tight for Hausdorff clustering
    job = await _enqueue(queue, "match_route_job", activity_id=activity_id, user_id=user_id, timeout=120, heartbeat=60)
    return job.key if job else None


async def enqueue_segment_process_job(activity_id: str, user_id: int) -> str | None:
    """
    Enqueue segment processing for an activity.

    This job matches the activity against known segments and detects new climbs.
    Called after route matching completes.

    Returns job key or None if queue is not available.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Explicit timeout — SAQ default is 10s (ADR 0006, decision 4)
    job = await _enqueue(queue, "segment_process_job", activity_id=activity_id, user_id=user_id, timeout=120, heartbeat=60)
    return job.key if job else None


async def enqueue_retroactive_match_job(segment_id: str) -> str | None:
    """
    Enqueue retroactive matching for a newly created segment.

    This job scans historical activities to find those that match the segment.
    Should be called when a segment is created or approved.

    Returns job key or None if queue is not available.
    """
    if not queue_available():
        return None
    queue = await get_queue()
    # Retroactive matching can process many activities; give it longer timeout
    # group_key cap: at most one retroactive match active (ADR 0006, decision 4)
    job = await _enqueue(
        queue,
        "retroactive_match_job",
        segment_id=segment_id,
        timeout=600,
        group_key="retroactive_match",
        heartbeat=120,
    )
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
    # group_key cap: at most one batch weather active (ADR 0006, decision 4)
    job = await _enqueue(
        queue,
        "batch_weather_job",
        user_id=user_id,
        throttle_seconds=throttle_seconds,
        timeout=7200,  # 2 hour timeout
        group_key="batch_weather",
        heartbeat=120,
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
    # group_key cap + retries=1: a swept backup is never auto-retried (ADR 0006, decisions 2+4)
    job = await _enqueue(queue, "backup_job", timeout=1800, group_key="backup", retries=1, heartbeat=60)
    return job.key if job else None
