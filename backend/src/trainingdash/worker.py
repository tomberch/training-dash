"""
Background worker jobs for TrainingDash.

This module defines arq worker jobs for:
- FIT file ingestion (from uploads)
- Route matching
- Sync jobs for external integrations (Xert, Garmin)
- Nightly cron jobs to trigger syncs

The sync jobs use the common orchestration pattern from sync.py with
provider-specific implementations from sync_providers.py.
"""

import logging
import os
from contextlib import asynccontextmanager

from arq.cron import cron
from trainingdash.jobs import get_redis_settings, create_redis_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def worker_db_session():
    """Create a database session for worker jobs."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    db_url = os.environ.get("DATABASE_URL")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


async def ingest_job(ctx, user_id: int, fit_bytes: bytes, source: str, source_ref: str):
    """Ingest a FIT file and enqueue route matching."""
    from trainingdash.ingest import ingest_fit

    async with worker_db_session() as db:
        activity = await ingest_fit(db, user_id, fit_bytes, source, source_ref)
        if activity is None:
            return {"success": False, "activity_id": None}

        pool = await create_redis_pool()
        try:
            await pool.enqueue_job("match_route_job", activity_id=activity.id, user_id=user_id)
        finally:
            await pool.aclose()

        return {"success": True, "activity_id": activity.id}


async def match_route_job(ctx, activity_id: int, user_id: int):
    """Match an activity to a route cluster."""
    from sqlalchemy import select
    from trainingdash.models import Activity, Record
    from trainingdash.route_matching import find_or_create_route_id

    async with worker_db_session() as db:
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


async def sync_xert_job(ctx, user_id: int):
    """
    Sync activities from Xert for a user.
    
    Uses the common sync orchestration with XertSyncProvider.
    Activities are ingested via session_data (not FIT files) and
    routed through the full metric pipeline.
    """
    from trainingdash.sync import run_sync
    from trainingdash.sync_providers import XertSyncProvider
    
    async with worker_db_session() as db:
        provider = XertSyncProvider()
        result = await run_sync(db, user_id, provider)
        
        return {
            "success": result.success,
            "user_id": result.user_id,
            "synced_activities": result.synced_activities,
            "skipped_duplicates": result.skipped_duplicates,
            "error": result.error,
        }


async def sync_garmin_job(ctx, user_id: int):
    """
    Sync activities from Garmin Connect for a user.
    
    Uses the common sync orchestration with GarminSyncProvider.
    Activities are ingested via FIT file download through the
    standard ingest pipeline.
    """
    from trainingdash.sync import run_sync
    from trainingdash.sync_providers import GarminSyncProvider
    
    async with worker_db_session() as db:
        provider = GarminSyncProvider()
        result = await run_sync(db, user_id, provider)
        
        return {
            "success": result.success,
            "user_id": result.user_id,
            "synced_activities": result.synced_activities,
            "skipped_duplicates": result.skipped_duplicates,
            "error": result.error,
        }


async def hourly_sync_scheduler(ctx):
    """
    Hourly cron job: enqueue sync jobs for users whose sync_hour matches current hour.
    
    Garmin syncs are enqueued immediately (at :00).
    Xert syncs are deferred by 15 minutes to stagger API calls.
    """
    from datetime import datetime, timezone
    from sqlalchemy import select
    from trainingdash.models import GarminCredentials, XertCredentials, User
    
    current_hour = datetime.now(timezone.utc).hour
    logger.info(f"hourly_sync_scheduler: Running for hour {current_hour}")
    
    async with worker_db_session() as db:
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
    
    pool = await create_redis_pool()
    try:
        # Enqueue Garmin syncs immediately
        for user_id in garmin_user_ids:
            await pool.enqueue_job("sync_garmin_job", user_id=user_id)
            logger.info(f"hourly_sync_scheduler: Enqueued Garmin sync for user {user_id}")
        
        # Enqueue Xert syncs with 15 minute delay to stagger
        from datetime import timedelta
        defer_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        for user_id in xert_user_ids:
            await pool.enqueue_job("sync_xert_job", user_id=user_id, _defer_until=defer_until)
            logger.info(f"hourly_sync_scheduler: Enqueued Xert sync for user {user_id} (deferred 15min)")
    finally:
        await pool.aclose()
    
    logger.info(f"hourly_sync_scheduler: Queued {len(garmin_user_ids)} Garmin, {len(xert_user_ids)} Xert syncs")
    return {"success": True, "garmin_queued": len(garmin_user_ids), "xert_queued": len(xert_user_ids)}


class WorkerSettings:
    functions = [
        ingest_job,
        match_route_job,
        sync_xert_job,
        sync_garmin_job,
        hourly_sync_scheduler,
    ]
    redis_settings = get_redis_settings()
    max_tries = 3
    retry_delay = 10  # seconds between retries
    job_timeout = 300  # 5 minutes max per job
    
    # Cron schedule: run the sync scheduler at the top of every hour
    cron_jobs = [
        cron(hourly_sync_scheduler, minute=0, unique=True),
    ]
