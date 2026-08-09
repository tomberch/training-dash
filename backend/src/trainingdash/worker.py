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

from trainingdash.queue import get_queue
from trainingdash.integrations.xert.mock_client import setup_mock_xert_client

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


async def ingest_job(ctx: dict, *, user_id: int, fit_bytes: bytes, source: str, source_ref: str):
    """Ingest a FIT file and enqueue route matching."""
    from trainingdash.use_cases import IngestActivity

    async with worker_db_session(ctx) as db:
        use_case = IngestActivity(db)
        activity = await use_case.execute(user_id, fit_bytes, source, source_ref)
        if activity is None:
            return {"success": False, "activity_id": None}

        queue = await get_queue()
        await queue.enqueue("match_route_job", activity_id=activity.id, user_id=user_id)

        return {"success": True, "activity_id": activity.id}


async def match_route_job(ctx: dict, *, activity_id: int, user_id: int):
    """Match an activity to a route cluster."""
    from sqlalchemy import select
    from trainingdash.repositories.postgres.models import Activity, Record
    from trainingdash.route_matching import find_or_create_route_id

    async with worker_db_session(ctx) as db:
        result = await db.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one_or_none()
        if activity is None:
            return {"success": False}

        records_result = await db.execute(
            select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
        )
        all_records = records_result.scalars().all()
        route_id = await find_or_create_route_id(db, activity, all_records)
        if route_id is not None:
            activity.route_id = route_id
            await db.commit()
        return {"success": True, "route_id": route_id}


async def recalculate_after_delete_job(ctx: dict, *, user_id: int) -> dict:
    """
    Recompute fitness model and breakthrough flags after an activity is deleted.

    Runs asynchronously so the DELETE endpoint returns 204 immediately.
    Steps:
      1. Recompute FitnessHistory (CP model) from remaining activities.
      2. Re-evaluate is_breakthrough flags on all remaining activities.

    Idempotent — safe to re-run after partial failure.
    """
    import logging

    from sqlalchemy import select
    from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower
    from trainingdash.ingest import _update_fitness_model
    from trainingdash.domain.fitness import detect_breakthrough, get_all_time_bests

    logger = logging.getLogger(__name__)

    async with worker_db_session(ctx) as db:
        # Step 1: Recompute fitness model (FitnessHistory snapshot)
        try:
            await _update_fitness_model(db, user_id)
        except Exception:
            logger.exception(
                "recalculate_after_delete_job: fitness model update failed for user %s",
                user_id,
            )

        # Step 2: Re-evaluate is_breakthrough on all remaining activities
        try:
            activities_result = await db.execute(
                select(Activity)
                .where(Activity.user_id == user_id)
                .order_by(Activity.started_at.asc())
            )
            activities = activities_result.scalars().all()

            if activities:
                # Load all peak powers for this user's activities
                activity_ids = [a.id for a in activities]
                peaks_result = await db.execute(
                    select(ActivityPeakPower).where(
                        ActivityPeakPower.activity_id.in_(activity_ids)
                    )
                )
                all_peaks = peaks_result.scalars().all()

                peaks_by_activity: dict = {}
                for p in all_peaks:
                    peaks_by_activity.setdefault(p.activity_id, {})[p.duration_seconds] = p.watts

                # Walk chronologically, re-evaluating breakthroughs
                seen_peaks: list[dict[int, int]] = []
                for activity in activities:
                    activity_peaks = peaks_by_activity.get(activity.id, {})
                    all_time_bests = get_all_time_bests(seen_peaks)
                    is_bt = detect_breakthrough(activity_peaks, all_time_bests) if activity_peaks else False
                    if activity.is_breakthrough != is_bt:
                        activity.is_breakthrough = is_bt
                    if activity_peaks:
                        seen_peaks.append(activity_peaks)

                await db.commit()

        except Exception:
            logger.exception(
                "recalculate_after_delete_job: breakthrough re-evaluation failed for user %s",
                user_id,
            )

        return {"success": True, "user_id": user_id}


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
    """
    Hourly cron job: enqueue sync jobs for users whose sync_hour matches current hour.
    
    Garmin syncs are enqueued immediately (at :00).
    Xert syncs are deferred by 15 minutes to stagger API calls.
    """
    from sqlalchemy import select
    from trainingdash.repositories.postgres.models import GarminCredentials, XertCredentials, User
    
    current_hour = datetime.now(timezone.utc).hour
    logger.info(f"hourly_sync_scheduler: Running for hour {current_hour}")
    
    async with worker_db_session(ctx) as db:
        # Find users with this sync_hour who have Garmin credentials
        garmin_result = await db.execute(
            select(GarminCredentials.user_id)
            .join(User, User.id == GarminCredentials.user_id)
            .where(User.sync_hour == current_hour)
        )
        garmin_user_ids = garmin_result.scalars().all()
        
        # Find users with this sync_hour who have Xert credentials
        xert_result = await db.execute(
            select(XertCredentials.user_id)
            .join(User, User.id == XertCredentials.user_id)
            .where(User.sync_hour == current_hour)
        )
        xert_user_ids = xert_result.scalars().all()
    
    if not garmin_user_ids and not xert_user_ids:
        logger.info(f"hourly_sync_scheduler: No users scheduled for hour {current_hour}")
        return {"success": True, "garmin_queued": 0, "xert_queued": 0}
    
    queue = await get_queue()
    
    # Enqueue Garmin syncs immediately
    for user_id in garmin_user_ids:
        await queue.enqueue("sync_garmin_job", user_id=user_id)
        logger.info(f"hourly_sync_scheduler: Enqueued Garmin sync for user {user_id}")
    
    # Enqueue Xert syncs with 15 minute delay to stagger
    import time
    defer_until = time.time() + (15 * 60)  # 15 minutes from now
    for user_id in xert_user_ids:
        await queue.enqueue("sync_xert_job", user_id=user_id, scheduled=defer_until)
        logger.info(f"hourly_sync_scheduler: Enqueued Xert sync for user {user_id} (deferred 15min)")
    
    logger.info(f"hourly_sync_scheduler: Queued {len(garmin_user_ids)} Garmin, {len(xert_user_ids)} Xert syncs")
    return {"success": True, "garmin_queued": len(garmin_user_ids), "xert_queued": len(xert_user_ids)}


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
async def get_settings() -> dict:
    """
    Return SAQ worker settings.
    
    This is a callable that returns the settings dict, allowing
    lazy initialization of the queue connection.
    """
    queue = await get_queue()
    
    return {
        "queue": queue,
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


# For `saq trainingdash.worker.settings` command
settings = get_settings
