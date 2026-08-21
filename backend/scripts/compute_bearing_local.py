#!/usr/bin/env python3
"""Compute direction bearings for specific activities - runs locally against Docker DB.

Usage:
    cd backend && python scripts/compute_bearing_local.py
"""

import asyncio
import sys

sys.path.insert(0, "src")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def compute_bearings():
    from trainingdash.domain.direction import compute_direction_bearings

    # Connect to Docker DB
    engine = create_async_engine("postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    activity_ids = [
        "4814419e-fa07-48fc-9d8f-65b25756c0be",  # Schwarzenburg
        "9bdb7f7d-389d-4af9-949f-dcfbfbac27bb",  # Rüschegg
    ]

    async with async_session() as session:
        for activity_id in activity_ids:
            # Get GPS data using raw SQL to avoid ORM overhead
            result = await session.execute(
                text("""
                    SELECT lat, lon, distance_m 
                    FROM records 
                    WHERE activity_id = :activity_id 
                      AND lat IS NOT NULL 
                      AND lon IS NOT NULL
                    ORDER BY timestamp
                """),
                {"activity_id": activity_id},
            )
            rows = result.fetchall()

            if not rows:
                print(f"Activity {activity_id}: No GPS data")
                continue

            gps_points = [(row[0], row[1], row[2]) for row in rows]
            bearings = compute_direction_bearings(gps_points)

            print(f"Activity {activity_id}:")
            print(f"  GPS points: {len(gps_points)}")
            print(f"  Bearing at 25%: {bearings.bearing_25}°")
            print(f"  Bearing at 50%: {bearings.bearing_75}°")

            # Update the activity
            await session.execute(
                text("""
                    UPDATE activities 
                    SET direction_bearing = :b25, direction_bearing_75 = :b50
                    WHERE id = :id
                """),
                {"b25": bearings.bearing_25, "b50": bearings.bearing_75, "id": activity_id},
            )
            await session.commit()
            print("  Updated!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(compute_bearings())
