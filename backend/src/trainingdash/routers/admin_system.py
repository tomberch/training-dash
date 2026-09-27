"""Admin System Dashboard API endpoints.

Provides endpoints for the Admin System Dashboard:
- Events: paginated, filterable system event log
- Jobs: active/queued SAQ background jobs
- Cache Stats: current counters, historical data, and cache sizes
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, text

from trainingdash import cache_stats
from trainingdash.auth import AdminUser, DbSession
from trainingdash.dependencies import EventRepoD
from trainingdash.repositories.postgres.models import CacheStats, Event, User

router = APIRouter(prefix="/api/admin/system", tags=["admin-system"])


# --- Events endpoint ---


class EventResponse(BaseModel):
    """Single event in the response."""

    id: int
    created_at: datetime
    event_type: str
    outcome: str
    user_id: int | None
    user_email: str | None
    payload: dict


class EventsListResponse(BaseModel):
    """Response for events list endpoint."""

    events: list[EventResponse]
    total: int


@router.get("/events", response_model=EventsListResponse)
async def get_system_events(
    admin: AdminUser,
    db: DbSession,
    event_repo: EventRepoD,
    event_type: str | None = Query(None, description="Filter by exact event type"),
    outcome: str | None = Query(None, description="Filter by outcome (success, failure, info)"),
    user_id: int | None = Query(None, description="Filter by user ID"),
    since: datetime | None = Query(None, description="Events after this time (ISO format)"),
    until: datetime | None = Query(None, description="Events before this time (ISO format)"),
    limit: int = Query(50, ge=1, le=100, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
):
    """
    Get paginated, filterable system events.

    Returns events ordered by created_at descending (newest first).
    Includes user email for events with a user_id.
    """
    # Build query with left join to get user email
    query = select(Event, User.email).outerjoin(User, Event.user_id == User.id)

    # Apply filters
    if event_type is not None:
        query = query.where(Event.event_type == event_type)
    if outcome is not None:
        query = query.where(Event.outcome == outcome)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)
    if since is not None:
        query = query.where(Event.created_at >= since)
    if until is not None:
        query = query.where(Event.created_at < until)

    query = query.order_by(Event.created_at.desc()).limit(min(limit, 100)).offset(offset)

    result = await db.execute(query)
    rows = result.all()

    events = [
        EventResponse(
            id=event.id,
            created_at=event.created_at,
            event_type=event.event_type,
            outcome=event.outcome,
            user_id=event.user_id,
            user_email=email,
            payload=event.payload,
        )
        for event, email in rows
    ]

    total = await event_repo.count(
        event_type=event_type,
        outcome=outcome,
        user_id=user_id,
        since=since,
        until=until,
    )

    return EventsListResponse(events=events, total=total)


# --- Jobs endpoint ---


class JobResponse(BaseModel):
    """Single job in the response."""

    key: str
    function: str
    status: str
    scheduled: datetime | None
    started: datetime | None
    kwargs: dict | None
    attempts: int = 0


class JobsListResponse(BaseModel):
    """Response for jobs list endpoint."""

    jobs: list[JobResponse]
    workers_alive: int = 0


@router.get("/jobs", response_model=JobsListResponse)
async def get_active_jobs(
    admin: AdminUser,
    db: DbSession,
):
    """
    Get recent background jobs from SAQ (ADR 0007).

    Includes non-terminal (active/queued) and terminal (failed/aborted) rows —
    SAQ retains terminal rows ~600s, so failed jobs show as a recent tail —
    with per-job attempt counts and live-worker liveness for the dashboard.
    """
    jobs = []
    try:
        result = await db.execute(
            text("""
                SELECT
                    key,
                    convert_from(job, 'utf8')::jsonb->>'function' as function,
                    status,
                    to_timestamp(scheduled::double precision) as scheduled,
                    to_timestamp(NULLIF(convert_from(job, 'utf8')::jsonb->>'started', '')::double precision) as started,
                    convert_from(job, 'utf8')::jsonb->'kwargs' as kwargs,
                    COALESCE(convert_from(job, 'utf8')::jsonb->>'attempts', '0') as attempts
                FROM saq_jobs
                WHERE status IN ('active', 'queued', 'failed', 'aborted', 'aborting')
                ORDER BY scheduled DESC
                LIMIT 100
            """)
        )
        for row in result.fetchall():
            jobs.append(
                JobResponse(
                    key=row.key,
                    function=row.function or "unknown",
                    status=row.status,
                    scheduled=row.scheduled,
                    started=row.started,
                    kwargs=row.kwargs,
                    attempts=int(row.attempts or 0),
                )
            )
    except Exception:
        # saq_jobs missing/mismatched schema (worker never ran) — empty list.
        jobs = []

    # Worker liveness (ADR 0007): saq_stats rows are TTL-filtered by SAQ (60s).
    workers_alive = 0
    try:
        stats = await db.execute(
            text("""
                SELECT count(*) FROM saq_stats
                WHERE expire_at >= EXTRACT(EPOCH FROM NOW())
            """)
        )
        workers_alive = int(stats.scalar() or 0)
    except Exception:
        workers_alive = 0

    return JobsListResponse(jobs=jobs, workers_alive=workers_alive)


# --- Job action endpoints (ADR 0007) ---


class JobActionResponse(BaseModel):
    """Result of a job operation (abort/retry)."""

    success: bool
    message: str | None = None


def _audit_log(db, admin, action: str, target_user_id: int | None, summary: str) -> None:
    """Record a job operation in the Audit Log (ADR 0007: all job ops audited)."""
    from trainingdash.repositories.postgres.models import AuditLog

    db.add(
        AuditLog(
            admin_id=admin.id,
            action=action,
            target_user_id=target_user_id,
            target_user_email=getattr(admin, "email", "") or "",
            summary=summary,
        )
    )


@router.post("/jobs/{job_key}/abort", response_model=JobActionResponse)
async def abort_job(
    job_key: str,
    admin: AdminUser,
    db: DbSession,
):
    """Abort a stuck or queued job (ADR 0007).

    SAQ delivers the abort cross-process within ~1s (two-phase: aborting →
    aborted). Aborting a mid-run backup is allowed (escape hatch) and audited;
    the strand-recovery cron marks its history row failed (ADR 0006).
    """
    from trainingdash.queue import get_queue

    queue = await get_queue()
    try:
        job = await queue.job(job_key)
        if job is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Job {job_key} not found")
        await queue.abort(job, error="aborted by admin")
    except HTTPException:
        raise
    except Exception as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Job queue not available") from exc

    _audit_log(db, admin, "job.abort", None, f"Aborted job {job_key}")
    await db.commit()

    return JobActionResponse(success=True, message=f"Abort requested for {job_key}")


@router.post("/jobs/{job_key}/retry", response_model=JobActionResponse)
async def retry_failed_job(
    job_key: str,
    admin: AdminUser,
    db: DbSession,
    event_repo: EventRepoD,
):
    """Re-enqueue a failed job from its dead-letter event (ADR 0007).

    The dead-letter ``job.failed`` event carries the original kwargs; the retry
    runs under a fresh SAQ key so it always fires (manual-trigger semantics).
    """
    from trainingdash.jobs import EnqueueError, get_retry_enqueue

    # Find the most recent dead-letter event for this job key
    result = await db.execute(
        text("""
            SELECT payload FROM events
            WHERE event_type = 'job.failed'
              AND payload->>'dead_letter' = 'true'
              AND payload->>'job_key' = :job_key
            ORDER BY created_at DESC
            LIMIT 1
        """).bindparams(job_key=job_key)
    )
    row = result.first()
    if row is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No dead-letter event found for this job key")

    payload = row[0]
    job_name = payload.get("job_name")
    kwargs = payload.get("kwargs") or {}

    enqueue_fn = get_retry_enqueue(job_name)
    if enqueue_fn is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"Job {job_name} is not retryable via the admin surface")

    # The dead-letter payload stores SAQ-serialized kwargs (fit_bytes_b64 etc.);
    # the helper expects the pre-encoding form (fit_bytes) — decode it back.
    if "fit_bytes_b64" in kwargs and job_name == "ingest":
        import base64

        kwargs = dict(kwargs)
        kwargs["fit_bytes"] = base64.b64decode(kwargs.pop("fit_bytes_b64"))

    try:
        await enqueue_fn(**kwargs)
    except EnqueueError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Job queue not available") from exc
    except TypeError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=f"Stored kwargs no longer match the job signature: {exc}") from exc

    _audit_log(db, admin, "job.retry", None, f"Retried job {job_name} (dead-letter {job_key})")
    await db.commit()

    return JobActionResponse(success=True, message=f"Retry enqueued for {job_name}")


class CacheTypeStats(BaseModel):
    """Hit/miss stats for a cache type."""

    hits: int
    misses: int


class CacheHistoryEntry(BaseModel):
    """Historical cache stats bucket."""

    bucket_start: datetime
    cache_type: str
    hits: int
    misses: int

    model_config = {"from_attributes": True}


class CacheSizes(BaseModel):
    """Cache storage sizes."""

    tiles_mb: float
    geocoding_count: int


class CacheStatsResponse(BaseModel):
    """Response for cache stats endpoint."""

    current: dict[str, CacheTypeStats]
    history: list[CacheHistoryEntry]
    sizes: CacheSizes


def _get_directory_size_mb(path: Path) -> float:
    """Get total size of a directory in MB."""
    if not path.exists():
        return 0.0

    total_bytes = 0
    try:
        for file in path.rglob("*"):
            if file.is_file():
                total_bytes += file.stat().st_size
    except (OSError, PermissionError):
        pass

    return round(total_bytes / (1024 * 1024), 2)


@router.get("/cache-stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    admin: AdminUser,
    db: DbSession,
    days: int = Query(7, ge=1, le=90, description="Days of history to return"),
):
    """
    Get cache statistics: current session counters, historical data, and sizes.

    - current: Real-time in-memory counters (since last flush)
    - history: Historical hourly buckets from database
    - sizes: Tile cache size on disk, geocoding cache entry count
    """
    # Current in-memory counters
    counters = cache_stats.get_current()

    current_stats: dict[str, CacheTypeStats] = {}

    # Combine tiles_osm and tiles_carto into "tiles" for display
    tiles_hits = counters.hits.get("tiles_osm", 0) + counters.hits.get("tiles_carto", 0)
    tiles_misses = counters.misses.get("tiles_osm", 0) + counters.misses.get("tiles_carto", 0)
    if tiles_hits > 0 or tiles_misses > 0:
        current_stats["tiles"] = CacheTypeStats(hits=tiles_hits, misses=tiles_misses)

    geocoding_hits = counters.hits.get("geocoding", 0)
    geocoding_misses = counters.misses.get("geocoding", 0)
    if geocoding_hits > 0 or geocoding_misses > 0:
        current_stats["geocoding"] = CacheTypeStats(hits=geocoding_hits, misses=geocoding_misses)

    # Historical data from database
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    result = await db.execute(
        select(CacheStats)
        .where(CacheStats.bucket_start >= since)
        .order_by(CacheStats.bucket_start.desc())
        .limit(days * 24 * 3)  # Max 3 cache types × 24 hours × days
    )
    history_rows = result.scalars().all()
    history = [CacheHistoryEntry.model_validate(row) for row in history_rows]

    # Cache sizes
    tile_cache_dir = Path(os.environ.get("TILE_CACHE_DIR", "/app/tile-cache"))
    tiles_mb = _get_directory_size_mb(tile_cache_dir)

    # Geocoding cache count (raw SQL since it's not a model)
    geocoding_count_result = await db.execute(text("SELECT COUNT(*) FROM geocoding_cache"))
    geocoding_count = geocoding_count_result.scalar() or 0

    return CacheStatsResponse(
        current=current_stats,
        history=history,
        sizes=CacheSizes(tiles_mb=tiles_mb, geocoding_count=geocoding_count),
    )
