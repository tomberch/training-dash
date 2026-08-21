#!/usr/bin/env python3
"""Update direction bearings for two specific activities.

Usage:
    docker exec traindash-dev-app-1 python scripts/update_two_bearings.py
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def update_bearings():
    from trainingdash.domain.direction import compute_direction_bearings
    from trainingdash.repositories.postgres.models import Activity, Record

    engine = create_async_engine("postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    activity_ids = [
        "4814419e-fa07-48fc-9d8f-65b25756c0be",  # Schwarzenburg
        "9bdb7f7d-389d-4af9-949f-dcfbfbac27bb",  # Rüschegg
    ]

    async with async_session() as session:
        for activity_id in activity_ids:
            result = await session.execute(select(Activity).where(Activity.id == activity_id))
            activity = result.scalar_one_or_none()
            if not activity:
                print(f"Activity {activity_id} not found")
                continue

            # Load GPS records
            records_result = await session.execute(
                select(Record).where(Record.activity_id == activity.id).order_by(Record.timestamp)
            )
            records = list(records_result.scalars().all())

            # Compute direction bearings (25% and 50%)
            gps_points = [(r.lat, r.lon, r.distance_m) for r in records if r.lat is not None and r.lon is not None]
            bearings = compute_direction_bearings(gps_points)

            print(f"Activity {activity_id}:")
            print(f"  Route ID: {activity.route_id}")
            print(f"  Old bearings: 25%={activity.direction_bearing}, 75%={activity.direction_bearing_75}")
            print(f"  New bearings: 25%={bearings.bearing_25}, 50%={bearings.bearing_75}")

            activity.direction_bearing = bearings.bearing_25
            activity.direction_bearing_75 = bearings.bearing_75
            await session.commit()
            print("  Updated!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(update_bearings())
