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
from datetime import datetime, timedelta, timezone

from saq import CronJob
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncEngine

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
    from trainingdash.use_cases import SyncFromProvider
    from trainingdash.sync_providers import XertSyncProvider
    
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
    from trainingdash.use_cases import SyncFromProvider
    from trainingdash.sync_providers import GarminSyncProvider
    
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
    from trainingdash.use_cases import RecalculateMetrics
    from trainingdash.repositories.postgres.recalculation_job_repo import (
        PostgresRecalculationJobRepo,
    )
    
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
        ],
        "concurrency": 10,
        "startup": startup,
        "shutdown": shutdown,
        # Cron schedule: run the sync scheduler at the top of every hour
        "cron_jobs": [
            CronJob(hourly_sync_scheduler, cron="0 * * * *", unique=True),
        ],
    }
