#!/usr/bin/env python3
"""Backfill segment processing for activities ingested before job chaining.

Before the import path chained segment_process_job, activities from
Xert/Garmin imports were never matched against segments and never fed
climb detection. This script reprocesses every activity through
ProcessActivitySegments — in chronological order, so repetition counts
accumulate the way they would have live.

Idempotency: an activity is skipped when it already has segment efforts
or is the source of an existing suggested segment — running the script
twice produces the same result.

Usage:
    docker exec traindash-dev-app-1 python scripts/backfill_segment_processing.py
"""

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


async def backfill(db_url: str) -> None:
    from trainingdash.repositories.postgres.models import (
        Activity,
        Record,
        Segment,
        SegmentEffort,
    )
    from trainingdash.repositories.postgres.segment_repo import (
        PostgresSegmentEffortRepo,
        PostgresSegmentRepo,
        PostgresSegmentSuggestionRepo,
    )
    from trainingdash.use_cases.process_activity_segments import ProcessActivitySegments

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Idempotency set: activities that already have efforts
        efforts_result = await session.execute(select(SegmentEffort.activity_id).distinct())
        processed_by_effort = {row[0] for row in efforts_result}

        # Activities that already produced a suggested segment
        sources_result = await session.execute(
            select(Segment.source_activity_id).where(Segment.source_activity_id.isnot(None))
        )
        processed_by_source = {row[0] for row in sources_result}

        skip = processed_by_effort | processed_by_source

        result = await session.execute(select(Activity).order_by(Activity.started_at))
        activities = list(result.scalars().all())
        logger.info(f"Found {len(activities)} activities, {len(skip)} already processed")

        segment_repo = PostgresSegmentRepo(session)
        effort_repo = PostgresSegmentEffortRepo(session)
        suggestion_repo = PostgresSegmentSuggestionRepo(session)
        use_case = ProcessActivitySegments(session, segment_repo, effort_repo, suggestion_repo)

        totals = {"matched": 0, "climbs": 0, "prs": 0, "skipped": 0, "failed": 0}

        for i, activity in enumerate(activities, 1):
            if activity.id in skip:
                totals["skipped"] += 1
                continue

            records_result = await session.execute(
                select(Record).where(Record.activity_id == activity.id).order_by(Record.timestamp)
            )
            records = list(records_result.scalars().all())
            if len(records) < 2:
                logger.info(f"  [{i}/{len(activities)}] {activity.id}: insufficient records, skipping")
                continue

            try:
                result_stats = await use_case.execute(activity.id, activity.user_id)
                totals["matched"] += result_stats.matched_efforts
                totals["climbs"] += result_stats.detected_climbs
                totals["prs"] += result_stats.new_prs
                logger.info(
                    f"  [{i}/{len(activities)}] {activity.id}: "
                    f"efforts={result_stats.matched_efforts} climbs={result_stats.detected_climbs} "
                    f"prs={result_stats.new_prs}"
                )
            except Exception:
                totals["failed"] += 1
                logger.exception(f"  [{i}/{len(activities)}] {activity.id}: FAILED")

        logger.info(
            f"\nDone! efforts={totals['matched']} climbs={totals['climbs']} "
            f"prs={totals['prs']} skipped={totals['skipped']} failed={totals['failed']}"
        )

    await engine.dispose()


def main() -> None:
    import os

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash"
    )
    # SQLAlchemy async engine needs the asyncpg driver even when the env
    # var uses the default driver name
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    asyncio.run(backfill(db_url))


if __name__ == "__main__":
    main()