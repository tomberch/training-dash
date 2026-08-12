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
from trainingdash.repositories.postgres.models import CacheStats

router = APIRouter(prefix="/api/admin/system", tags=["admin-system"])


# --- Events endpoint ---


class EventResponse(BaseModel):
    """Single event in the response."""

    id: int
    created_at: datetime
    event_type: str
    outcome: str
    user_id: int | None
    payload: dict

    model_config = {"from_attributes": True}


class EventsListResponse(BaseModel):
    """Response for events list endpoint."""

    events: list[EventResponse]
    total: int


@router.get("/events", response_model=EventsListResponse)
async def get_system_events(
    admin: AdminUser,
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
    """
    events = await event_repo.list(
        event_type=event_type,
        outcome=outcome,
        user_id=user_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    total = await event_repo.count(
        event_type=event_type,
        outcome=outcome,
        user_id=user_id,
        since=since,
        until=until,
    )

    return EventsListResponse(
        events=[EventResponse.model_validate(e) for e in events],
        total=total,
    )


# --- Jobs endpoint ---


class JobResponse(BaseModel):
    """Single job in the response."""

    key: str
    function: str
    status: str
    scheduled: datetime | None
    started: datetime | None
    kwargs: dict | None


class JobsListResponse(BaseModel):
    """Response for jobs list endpoint."""

    jobs: list[JobResponse]


@router.get("/jobs", response_model=JobsListResponse)
async def get_active_jobs(
    admin: AdminUser,
    db: DbSession,
):
    """
    Get active and queued background jobs from SAQ.

    Queries the saq_jobs table for jobs with status 'active' or 'queued'.
    """
    # Query SAQ's jobs table directly
    # SAQ stores jobs in saq_jobs with columns: key, job (JSONB), queue, status, scheduled
    result = await db.execute(
        text("""
            SELECT 
                key,
                job->>'function' as function,
                status,
                scheduled,
                (job->>'started')::timestamptz as started,
                job->'kwargs' as kwargs
            FROM saq_jobs
            WHERE status IN ('active', 'queued')
            ORDER BY scheduled DESC
            LIMIT 100
        """)
    )

    jobs = []
    for row in result.fetchall():
        jobs.append(
            JobResponse(
                key=row.key,
                function=row.function or "unknown",
                status=row.status,
                scheduled=row.scheduled,
                started=row.started,
                kwargs=row.kwargs,
            )
        )

    return JobsListResponse(jobs=jobs)


# --- Cache Stats endpoint ---


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
