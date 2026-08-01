import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fitter.jobs import get_redis_settings, create_redis_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def worker_db_session():
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
    from fitter.ingest import ingest_fit

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
    from sqlalchemy import select
    from fitter.models import Activity, Record
    from fitter.route_matching import find_or_create_route_id

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


async def _create_activity_from_xert(
    db,
    user_id: int,
    detail,  # XertActivityDetail
    source_ref: str,
):
    """
    Create Activity and Record entries from Xert session_data.
    
    This converts Xert's JSON session_data format to our Activity/Record models.
    The same approach is used by Golden Cheetah's Xert integration.
    """
    from datetime import timedelta
    from geoalchemy2 import WKTElement
    from fitter.models import Activity, Record
    
    # Calculate summary stats from session_data
    total_distance_m = detail.distance * 1000 if detail.distance else 0
    elapsed_time_s = int(detail.duration) if detail.duration else 0
    
    # Create Activity - use naive datetime (DB is TIMESTAMP WITHOUT TIME ZONE)
    started_at = detail.started_at
    if started_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=None)
    
    activity = Activity(
        user_id=user_id,
        started_at=started_at,
        total_distance_m=total_distance_m,
        moving_time_s=elapsed_time_s,  # Xert doesn't distinguish moving vs elapsed
        elapsed_time_s=elapsed_time_s,
        source="xert",
        source_ref=source_ref,
        # Store XSS as training_load (Xert's equivalent to TSS)
        training_load=detail.xss,
    )
    db.add(activity)
    await db.flush()  # Get activity.id
    
    # Create Records from session_data
    if detail.session_data:
        first_time = detail.session_data[0].unix_time if detail.session_data else 0
        
        for point in detail.session_data:
            # Calculate timestamp from unix_time
            elapsed_secs = (point.unix_time - first_time) / 1000.0 if first_time else 0
            record_timestamp = started_at + timedelta(seconds=elapsed_secs)
            
            # Build geometry if lat/lng available
            geom = None
            if point.lat is not None and point.lng is not None:
                geom = WKTElement(f"POINT({point.lng} {point.lat})", srid=4326)
            
            # Speed is stored as m/s * 1000 in Xert, convert to m/s
            speed_mps = point.spd / 1000.0 if point.spd is not None else None
            
            record = Record(
                activity_id=activity.id,
                timestamp=record_timestamp,
                lat=point.lat,
                lon=point.lng,
                distance_m=point.dist if point.dist is not None else 0,
                hr_bpm=point.hr,
                power_w=int(point.power) if point.power is not None else None,
                speed_mps=speed_mps,
                altitude_m=point.alt,
                cadence_rpm=int(point.cad) if point.cad is not None else None,
                geom=geom,
            )
            db.add(record)
    
    await db.commit()
    return activity.id


async def sync_xert_job(ctx, user_id: int):
    """
    Sync activities from Xert for a user.
    
    - Decrypts stored Xert credentials
    - Logs in to Xert API (OAuth2 password grant)
    - Fetches activity list for last 90 days
    - Fetches full activity details with session_data for new activities
    - Creates Activity/Record entries directly from session_data
    
    Note: The Xert OAuth API does not provide FIT file downloads.
    We use the /oauth/activity/<path>?include_session_data=1 endpoint
    to get per-second data, same approach as Golden Cheetah.
    """
    import time
    from sqlalchemy import select
    from fitter.models import Activity, XertCredentials
    from fitter.crypto import decrypt, EncryptionError
    from fitter.xert import get_xert_client, XertAPIError
    
    async with worker_db_session() as db:
        # Get user's Xert credentials
        result = await db.execute(
            select(XertCredentials).where(XertCredentials.user_id == user_id)
        )
        creds = result.scalar_one_or_none()
        
        if creds is None:
            logger.warning(f"sync_xert_job: No Xert credentials for user {user_id}")
            return {"success": False, "user_id": user_id, "error": "No Xert credentials configured"}
        
        # Decrypt password
        try:
            xert_password = decrypt(creds.encrypted_password)
        except EncryptionError:
            logger.error(f"sync_xert_job: Failed to decrypt credentials for user {user_id}")
            return {"success": False, "user_id": user_id, "error": "Failed to decrypt credentials"}
        
        # Get existing source_refs to skip already-imported activities
        existing_result = await db.execute(
            select(Activity.source_ref).where(
                Activity.user_id == user_id,
                Activity.source == "xert",
            )
        )
        existing_refs = set(existing_result.scalars().all())
        
        # Connect to Xert
        client = get_xert_client()
        try:
            await client.login(creds.xert_email, xert_password)
            
            # List activities for last 90 days
            to_ts = int(time.time())
            from_ts = to_ts - (90 * 24 * 60 * 60)
            activities = await client.list_activities(from_timestamp=from_ts, to_timestamp=to_ts)
            
            # Filter to new activities
            new_activities = [a for a in activities if f"xert:{a.id}" not in existing_refs]
            
            if not new_activities:
                logger.info(f"sync_xert_job: No new activities for user {user_id}")
                return {"success": True, "user_id": user_id, "synced_activities": 0}
            
            # Fetch details and create activities for each new one
            synced = 0
            
            for xert_activity in new_activities:
                try:
                    source_ref = f"xert:{xert_activity.id}"
                    
                    # Fetch full activity detail with session_data
                    detail = await client.get_activity_detail(xert_activity, include_session_data=True)
                    
                    # Create Activity/Record directly from session_data
                    activity_id = await _create_activity_from_xert(
                        db, user_id, detail, source_ref
                    )
                    synced += 1
                    logger.info(f"sync_xert_job: Created activity {activity_id} from {source_ref} for user {user_id}")
                    
                except XertAPIError as e:
                    logger.warning(f"sync_xert_job: Failed to fetch activity {xert_activity.id}: {e}")
                    continue
                except Exception as e:
                    logger.exception(f"sync_xert_job: Unexpected error processing activity {xert_activity.id}")
                    continue
            
            logger.info(f"sync_xert_job: Synced {synced} activities for user {user_id}")
            return {"success": True, "user_id": user_id, "synced_activities": synced}
            
        except XertAPIError as e:
            logger.error(f"sync_xert_job: Xert API error for user {user_id}: {e}")
            return {"success": False, "user_id": user_id, "error": str(e)}
        finally:
            await client.close()


async def nightly_sync_all_xert(ctx):
    """
    Nightly cron job: enqueue sync_xert_job for every user with stored credentials.
    Runs at 2 AM daily.
    """
    from sqlalchemy import select
    from fitter.models import XertCredentials
    
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


class WorkerSettings:
    functions = [ingest_job, match_route_job, sync_xert_job, nightly_sync_all_xert]
    redis_settings = get_redis_settings()
    max_tries = 3
    retry_delay = 10  # seconds between retries
    job_timeout = 300  # 5 minutes max per job
    
    # Cron schedule: run nightly_sync_all_xert at 2 AM daily
    cron_jobs = [
        {
            "function": nightly_sync_all_xert,
            "cron": "0 2 * * *",  # 2 AM every day
            "unique": True,
        }
    ]