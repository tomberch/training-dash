#!/usr/bin/env python3
"""Re-match all activities to route clusters with the updated threshold.

This script:
1. Clears all existing route assignments
2. Deletes all existing routes
3. Re-runs route matching for all activities in chronological order

Usage:
    docker exec traindash-dev-app-1 python scripts/rematch_routes.py
"""

import asyncio
import logging

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def rematch_all_routes():
    from trainingdash.domain.direction import compute_direction_bearing
    from trainingdash.repositories.postgres.models import Activity, Record, Route
    from trainingdash.route_matching import HAUSDORFF_THRESHOLD_M, find_or_create_route_id

    engine = create_async_engine("postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        logger.info(f"Using Hausdorff threshold: {HAUSDORFF_THRESHOLD_M}m")

        # Count activities
        result = await session.execute(select(Activity).order_by(Activity.started_at))
        activities = result.scalars().all()
        logger.info(f"Found {len(activities)} activities to re-match")

        # Clear route assignments and delete routes
        logger.info("Clearing existing route assignments...")
        await session.execute(update(Activity).values(route_id=None, direction_bearing=None))
        await session.execute(text("DELETE FROM routes"))
        await session.commit()
        logger.info("Cleared all route data")

        # Re-match each activity in chronological order
        for i, activity in enumerate(activities, 1):
            # Load GPS records
            records_result = await session.execute(
                select(Record).where(Record.activity_id == activity.id).order_by(Record.timestamp)
            )
            records = list(records_result.scalars().all())

            if not records:
                logger.info(f"  [{i}/{len(activities)}] {activity.id}: No GPS records, skipping")
                continue

            # Compute direction bearing
            gps_points = [(r.lat, r.lon, r.distance_m) for r in records if r.lat is not None and r.lon is not None]
            direction_bearing = compute_direction_bearing(gps_points)

            # Match route
            route_id = await find_or_create_route_id(session, activity, records)

            if route_id is not None:
                activity.route_id = route_id
                activity.direction_bearing = direction_bearing
                await session.commit()
                logger.info(f"  [{i}/{len(activities)}] {activity.id}: route={route_id}, bearing={direction_bearing}")
            else:
                logger.info(f"  [{i}/{len(activities)}] {activity.id}: No route match (no GPS data)")

        # Summary
        result = await session.execute(select(Route))
        routes = result.scalars().all()
        logger.info(f"\nDone! Created {len(routes)} route clusters from {len(activities)} activities")

        for route in sorted(routes, key=lambda r: -r.ride_count)[:10]:
            logger.info(f"  Route {route.id}: {route.ride_count} rides")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(rematch_all_routes())
