from arq.connections import RedisSettings

from fitter.jobs import get_redis_settings


async def ingest_job(ctx, user_id: int, fit_bytes: bytes, source: str, source_ref: str):
    import os
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from fitter.ingest import ingest_fit

    db_url = os.environ.get("DATABASE_URL")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        activity = await ingest_fit(db, user_id, fit_bytes, source, source_ref)
        if activity is None:
            await engine.dispose()
            return {"success": False, "activity_id": None}

        # Enqueue route matching for this activity
        from arq import create_pool
        pool = await create_pool(get_redis_settings())
        await pool.enqueue_job("match_route_job", activity_id=activity.id, user_id=user_id)
        await pool.aclose()

        await engine.dispose()
        return {"success": True, "activity_id": activity.id}


async def match_route_job(ctx, activity_id: int, user_id: int):
    import os
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy import select, update
    from fitter.models import Activity, Record
    from fitter.route_matching import find_or_create_route_id

    db_url = os.environ.get("DATABASE_URL")
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one_or_none()
        if activity is None:
            await engine.dispose()
            return {"success": False}

        records_result = await db.execute(
            select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
        )
        all_records = records_result.scalars().all()
        route_id = await find_or_create_route_id(db, activity, all_records)
        if route_id is not None:
            activity.route_id = route_id
            await db.commit()
        await engine.dispose()
        return {"success": True, "route_id": route_id}


class WorkerSettings:
    functions = [ingest_job, match_route_job]
    redis_settings = get_redis_settings()