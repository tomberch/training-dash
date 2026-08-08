#!/usr/bin/env python3
"""Backfill map_polyline for existing activities.

Run from the backend directory:
    python scripts/backfill_polylines.py

Or with uv:
    uv run python scripts/backfill_polylines.py
"""

import asyncio
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from trainingdash.models import Activity, Record
from trainingdash.domain.polyline import generate_map_polyline


async def backfill_polylines(db_url: str) -> None:
    """Backfill map_polyline for all activities that don't have one."""
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Find activities without polylines
        result = await db.execute(
            select(Activity).where(Activity.map_polyline.is_(None))
        )
        activities = result.scalars().all()

        print(f"Found {len(activities)} activities without polylines")

        for i, activity in enumerate(activities):
            # Get records for this activity
            records_result = await db.execute(
                select(Record)
                .where(Record.activity_id == activity.id)
                .order_by(Record.timestamp)
            )
            records = records_result.scalars().all()

            # Convert to dict format
            records_dicts = [
                {"lat": r.lat, "lon": r.lon}
                for r in records
            ]

            # Generate polyline
            polyline = generate_map_polyline(records_dicts)

            if polyline:
                activity.map_polyline = polyline
                print(f"[{i+1}/{len(activities)}] Activity {activity.id}: {len(polyline)} chars")
            else:
                print(f"[{i+1}/{len(activities)}] Activity {activity.id}: no GPS data")

            # Commit in batches of 50
            if (i + 1) % 50 == 0:
                await db.commit()
                print(f"  Committed batch")

        # Final commit
        await db.commit()
        print("Done!")

    await engine.dispose()


if __name__ == "__main__":
    # Get database URL from environment or use default
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/trainingdash"
    )

    print(f"Connecting to database...")
    asyncio.run(backfill_polylines(db_url))
