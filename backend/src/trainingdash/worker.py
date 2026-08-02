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


async def nightly_sync_all_xert(ctx):
    """
    Nightly cron job: enqueue sync_xert_job for every user with stored credentials.
    Runs at 2 AM daily.
    """
    from sqlalchemy import select
    from trainingdash.models import XertCredentials
    
    async with worker_db_session() as db:
        result = await db.execute(select(XertCredentials.user_id))
        user_ids = result.scalars().all()
    
    if not user_ids:
        logger.info("nightly_sync_all_xert: No users with Xert credentials")
        return {"success": True, "users_queued": 0}
    
    pool = await create_redis_pool()
    try:
        for user_id in user_ids:
            await pool.enqueue_job("sync_xert_job", user_id=user_id)
            logger.info(f"nightly_sync_all_xert: Enqueued sync for user {user_id}")
    finally:
        await pool.aclose()
    
    logger.info(f"nightly_sync_all_xert: Enqueued {len(user_ids)} sync jobs")
    return {"success": True, "users_queued": len(user_ids)}


async def nightly_sync_all_garmin(ctx):
    """
    Nightly cron job: enqueue sync_garmin_job for every user with stored credentials.
    Runs at 3 AM daily (1 hour after Xert sync).
    """
    from sqlalchemy import select
    from trainingdash.models import GarminCredentials
    
    async with worker_db_session() as db:
        result = await db.execute(select(GarminCredentials.user_id))
        user_ids = result.scalars().all()
    
    if not user_ids:
        logger.info("nightly_sync_all_garmin: No users with Garmin credentials")
        return {"success": True, "users_queued": 0}
    
    pool = await create_redis_pool()
    try:
        for user_id in user_ids:
            await pool.enqueue_job("sync_garmin_job", user_id=user_id)
            logger.info(f"nightly_sync_all_garmin: Enqueued sync for user {user_id}")
    finally:
        await pool.aclose()
    
    logger.info(f"nightly_sync_all_garmin: Enqueued {len(user_ids)} sync jobs")
    return {"success": True, "users_queued": len(user_ids)}


class WorkerSettings:
    functions = [
        ingest_job,
        match_route_job,
        sync_xert_job,
        sync_garmin_job,
        nightly_sync_all_xert,
        nightly_sync_all_garmin,
    ]
    redis_settings = get_redis_settings()
    max_tries = 3
    retry_delay = 10  # seconds between retries
    job_timeout = 300  # 5 minutes max per job
    
    # Cron schedule:
    # - nightly_sync_all_xert at 2 AM daily
    # - nightly_sync_all_garmin at 3 AM daily (staggered 1 hour after Xert)
    cron_jobs = [
        cron(nightly_sync_all_xert, hour=2, minute=0, unique=True),
        cron(nightly_sync_all_garmin, hour=3, minute=0, unique=True),
    ]
