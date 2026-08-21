#!/usr/bin/env python3
"""Compute direction bearings for specific activities - memory efficient.

Usage:
    docker exec traindash-dev-app-1 python scripts/compute_bearing_batch.py
"""

import asyncio
import gc

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def compute_bearings():
    # Import inside function to minimize memory before connection
    from trainingdash.domain.direction import compute_direction_bearings

    # Connect to Docker DB
    engine = create_async_engine(
        "postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash",
        pool_size=1,
        max_overflow=0,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    activity_ids = [
        "4814419e-fa07-48fc-9d8f-65b25756c0be",  # Schwarzenburg
        "9bdb7f7d-389d-4af9-949f-dcfbfbac27bb",  # Rüschegg
    ]

    async with async_session() as session:
        for activity_id in activity_ids:
            print(f"Processing {activity_id}...")

            # Stream GPS data in batches to reduce memory
            gps_points = []
            offset = 0
            batch_size = 2000

            while True:
                result = await session.execute(
                    text("""
                        SELECT lat, lon, distance_m 
                        FROM records 
                        WHERE activity_id = :activity_id 
                          AND lat IS NOT NULL 
                          AND lon IS NOT NULL
                        ORDER BY timestamp
                        LIMIT :limit OFFSET :offset
                    """),
                    {"activity_id": activity_id, "limit": batch_size, "offset": offset},
                )
                rows = result.fetchall()

                if not rows:
                    break

                gps_points.extend((row[0], row[1], row[2]) for row in rows)
                offset += batch_size
                print(f"  Loaded {len(gps_points)} points...")

            if not gps_points:
                print("  No GPS data")
                continue

            bearings = compute_direction_bearings(gps_points)
            del gps_points  # Free memory
            gc.collect()

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
