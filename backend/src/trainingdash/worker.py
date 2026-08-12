"""
Background worker jobs for TrainingDash.

This module defines SAQ worker jobs for:
- FIT file ingestion (from uploads)
- Route matching
- Sync jobs for external integrations (Xert, Garmin)
- Hourly cron jobs to trigger syncs

The sync jobs use the common orchestration pattern from sync.py with
provider-specific implementations from sync_providers.py.

Engine lifecycle:
- A single SQLAlchemy async engine is created at worker startup via startup hook
- All jobs share this engine through the worker context (ctx)
- The engine is disposed at worker shutdown via shutdown hook
- This avoids the asyncpg InterfaceError that occurs when multiple engines
  share underlying connections under concurrent load
"""

import logging
import os
from contextlib import asynccontextmanager

from saq import CronJob
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from trainingdash.integrations.xert.mock_client import setup_mock_xert_client
from trainingdash.jobs import enqueue_match_route_job

logger = logging.getLogger(__name__)

# Initialize mock Xert client if enabled (for E2E testing)
setup_mock_xert_client()


async def startup(ctx: dict) -> None:
    """Create a shared database engine at worker startup."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable not set")

    engine = create_async_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = async_sessionmaker(engine, expire_on_commit=False)
    logger.info("Worker started: database engine created")


async def shutdown(ctx: dict) -> None:
    """Dispose the shared database engine at worker shutdown."""
    engine: AsyncEngine | None = ctx.get("db_engine")
    if engine is not None:
        await engine.dispose()
        logger.info("Worker shutdown: database engine disposed")


@asynccontextmanager
async def worker_db_session(ctx: dict):
    """Create a database session using the shared engine from worker context."""
    session_factory = ctx.get("db_session_factory")
    if session_factory is None:
        raise RuntimeError("Database session factory not initialized. Was startup called?")

    async with session_factory() as session:
        yield session


async def ingest_job(ctx: dict, *, user_id: int, fit_bytes_b64: str, source: str, source_ref: str):
    """Ingest a FIT file and enqueue route matching.

    Note: fit_bytes_b64 is base64-encoded because SAQ uses JSON serialization.
    """
    import base64

    from trainingdash.use_cases import IngestActivity

    # Decode base64 back to bytes
    fit_bytes = base64.b64decode(fit_bytes_b64)

    async with worker_db_session(ctx) as db:
        use_case = IngestActivity(db)
        activity = await use_case.execute(user_id, fit_bytes, source, source_ref)
        if activity is None:
            return {"success": False, "activity_id": None}

        await enqueue_match_route_job(str(activity.id), user_id)

        return {"success": True, "activity_id": str(activity.id)}


async def match_route_job(ctx: dict, *, activity_id: str, user_id: int):
    """Match an activity to a route cluster (thin dispatch to MatchRoute use case)."""
    from trainingdash.use_cases.match_route import MatchRoute

    async with worker_db_session(ctx) as db:
        return await MatchRoute(db).execute(activity_id, user_id)


async def recalculate_after_delete_job(ctx: dict, *, user_id: int) -> dict:
    """Recompute fitness model + breakthrough flags after a delete (thin dispatch)."""
    from trainingdash.use_cases.recalc_after_delete import RecalcAfterDelete

    async with worker_db_session(ctx) as db:
        return await RecalcAfterDelete(db).execute(user_id)


async def sync_xert_job(ctx: dict, *, user_id: int):
    """
    Sync activities from Xert for a user.

    Uses the SyncFromProvider use case with XertSyncProvider.
    Activities are ingested via session_data (not FIT files) and
    routed through the full metric pipeline.
    """
    from trainingdash.sync_providers import XertSyncProvider
    from trainingdash.use_cases import SyncFromProvider

    async with worker_db_session(ctx) as db:
        provider = XertSyncProvider()
        use_case = SyncFromProvider(db)
        result = await use_case.execute(user_id, provider)

        return {
            "success": result.success,
            "user_id": result.user_id,
            "synced_activities": result.synced_activities,
            "skipped_duplicates": result.skipped_duplicates,
            "error": result.error,
        }


async def sync_garmin_job(ctx: dict, *, user_id: int):
    """
    Sync activities from Garmin Connect for a user.

    Uses the SyncFromProvider use case with GarminSyncProvider.
    Activities are ingested via FIT file download through the
    standard ingest pipeline.
    """
    from trainingdash.sync_providers import GarminSyncProvider
    from trainingdash.use_cases import SyncFromProvider

    async with worker_db_session(ctx) as db:
        provider = GarminSyncProvider()
        use_case = SyncFromProvider(db)
        result = await use_case.execute(user_id, provider)

        return {
            "success": result.success,
            "user_id": result.user_id,
            "synced_activities": result.synced_activities,
            "skipped_duplicates": result.skipped_duplicates,
            "error": result.error,
        }


async def hourly_sync_scheduler(ctx: dict):
    """Hourly cron: enqueue sync jobs for users whose sync_hour matches (thin dispatch)."""
    from trainingdash.use_cases.hourly_sync_scheduler import HourlySyncScheduler

    async with worker_db_session(ctx) as db:
        return await HourlySyncScheduler(db).execute()


async def recalculate_metrics_job(ctx: dict, *, user_id: int) -> dict:
    """
    Recompute training metrics (NP, IF, TSS, W'bal, zone times) for all
    activities with power data that are missing metrics.

    Uses the RecalculateMetrics use case which tracks job status
    (pending → running → completed | failed) via RecalculationJobRepo.

    Returns a dict with success flag and count of activities updated.
    """
    from trainingdash.repositories.postgres.recalculation_job_repo import (
        PostgresRecalculationJobRepo,
    )
    from trainingdash.use_cases import RecalculateMetrics

    async with worker_db_session(ctx) as db:
        job_repo = PostgresRecalculationJobRepo(db)
        use_case = RecalculateMetrics(db, job_repo)
        result = await use_case.execute(user_id)

        return {
            "success": result.success,
            "user_id": result.user_id,
            "activities_updated": result.activities_updated,
            "error": result.error,
        }


async def flush_cache_stats(ctx: dict) -> dict:
    """
    Hourly cron: flush in-memory cache stats to the database.

    Reads current counters via get_and_reset() and upserts them
    into hourly buckets in cache_stats table.

    Runs at :05 past each hour to capture the previous hour's stats.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from trainingdash import cache_stats

    # Get and reset counters
    counters = cache_stats.get_and_reset()

    # Determine the bucket start (previous hour, since we run at :05)
    # This ensures stats are attributed to the hour they were collected in
    now = datetime.now(UTC).replace(tzinfo=None)
    bucket_start = (now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1))

    # Collect all cache types with data
    all_cache_types = set(counters.hits.keys()) | set(counters.misses.keys())

    if not all_cache_types:
        logger.info("flush_cache_stats: no data to flush")
        return {"flushed": 0}

    async with worker_db_session(ctx) as db:
        flushed = 0
        for cache_type in all_cache_types:
            hits = counters.hits.get(cache_type, 0)
            misses = counters.misses.get(cache_type, 0)

            if hits == 0 and misses == 0:
                continue

            # Upsert: add to existing bucket or insert new one
            await db.execute(
                text("""
                    INSERT INTO cache_stats (bucket_start, cache_type, hits, misses)
                    VALUES (:bucket_start, :cache_type, :hits, :misses)
                    ON CONFLICT (bucket_start, cache_type)
                    DO UPDATE SET
                        hits = cache_stats.hits + EXCLUDED.hits,
                        misses = cache_stats.misses + EXCLUDED.misses
                """),
                {
                    "bucket_start": bucket_start,
                    "cache_type": cache_type,
                    "hits": hits,
                    "misses": misses,
                },
            )
            flushed += 1

        await db.commit()
        logger.info(f"flush_cache_stats: flushed {flushed} cache types to bucket {bucket_start}")
        return {"flushed": flushed, "bucket_start": bucket_start.isoformat()}


async def prune_old_data(ctx: dict) -> dict:
    """
    Daily cron: delete events and cache_stats records older than 90 days.

    Events are deleted in batches of 1000 to avoid holding locks for too long.
    Cache stats are deleted in a single query (smaller table).

    Emits a cache.pruned event with deletion counts after completion.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete, select

    from trainingdash.domain.events import EventOutcome, EventType
    from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
    from trainingdash.repositories.postgres.models import CacheStats, Event

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=90)
    batch_size = 1000

    async with worker_db_session(ctx) as db:
        # Delete events in batches to avoid long locks
        events_deleted = 0
        while True:
            # Find IDs to delete (batched)
            id_query = (
                select(Event.id)
                .where(Event.created_at < cutoff)
                .limit(batch_size)
            )
            id_result = await db.execute(id_query)
            ids_to_delete = [row[0] for row in id_result.fetchall()]

            if not ids_to_delete:
                break

            # Delete the batch
            delete_query = delete(Event).where(Event.id.in_(ids_to_delete))
            result = await db.execute(delete_query)
            await db.commit()
            events_deleted += result.rowcount

        # Cache stats: smaller table, single delete is fine
        cache_result = await db.execute(
            delete(CacheStats).where(CacheStats.bucket_start < cutoff)
        )
        cache_deleted = cache_result.rowcount
        await db.commit()

        # Log the pruning event
        event_repo = PostgresEventRepo(db)
        await event_repo.log(
            event_type=EventType.CACHE_PRUNED.value,
            outcome=EventOutcome.INFO.value,
            user_id=None,
            payload={
                "events_deleted": events_deleted,
                "cache_stats_deleted": cache_deleted,
                "cutoff": cutoff.isoformat(),
            },
        )
        await db.commit()

    logger.info(
        f"prune_old_data: deleted {events_deleted} events, "
        f"{cache_deleted} cache_stats records older than {cutoff}"
    )

    return {
        "events_deleted": events_deleted,
        "cache_stats_deleted": cache_deleted,
    }


# SAQ worker settings - this is what `saq worker.settings` loads
# Note: SAQ supports settings as a callable, which delays queue creation
# until the worker actually starts. This is crucial for Docker Compose
# where the worker container may start before the database is ready.
def settings():
    """
    Return SAQ worker settings.

    This is a callable (not a dict) so that PostgresQueue.from_url() is not
    called at module import time. The queue connection is deferred until
    the worker process actually starts, giving the database container time
    to become healthy.
    """
    from saq.queue.postgres import PostgresQueue

    from trainingdash.queue import get_queue_url

    return {
        "queue": PostgresQueue.from_url(
            get_queue_url(),
            name="default",
            min_size=2,
            max_size=10,
        ),
        "functions": [
            ingest_job,
            match_route_job,
            recalculate_after_delete_job,
            recalculate_metrics_job,
            sync_xert_job,
            sync_garmin_job,
            hourly_sync_scheduler,
            flush_cache_stats,
            prune_old_data,
        ],
        "concurrency": 10,
        "startup": startup,
        "shutdown": shutdown,
        # Cron schedule: run the sync scheduler at the top of every hour,
        # flush cache stats at :05 past each hour, and prune old data daily at 4 AM
        "cron_jobs": [
            CronJob(hourly_sync_scheduler, cron="0 * * * *", unique=True),
            CronJob(flush_cache_stats, cron="5 * * * *", unique=True),
            CronJob(prune_old_data, cron="0 4 * * *", unique=True),
        ],
    }
