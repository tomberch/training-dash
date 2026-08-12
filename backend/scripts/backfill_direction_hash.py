#!/usr/bin/env python3
"""Backfill direction_hash for existing activities.

This script computes direction hashes for all activities that don't have one yet.
It processes activities in batches to avoid memory issues and commits after each batch.

Usage:
    cd backend
    uv run python scripts/backfill_direction_hash.py

    # Or with options:
    uv run python scripts/backfill_direction_hash.py --batch-size 50 --dry-run
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select, func

from trainingdash.repositories.postgres.db import async_session
from trainingdash.repositories.postgres.models import Activity, Record
from trainingdash.domain.direction import compute_direction_hash

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_direction_hashes(
    batch_size: int = 100,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[int, int]:
    """
    Backfill direction_hash for activities that don't have one.

    Args:
        batch_size: Number of activities to process per batch
        dry_run: If True, don't commit changes
        force: If True, recompute hashes for all activities

    Returns:
        Tuple of (processed_count, updated_count)
    """
    async with async_session() as db:
        # Count activities needing backfill
        if force:
            count_result = await db.execute(select(func.count(Activity.id)))
        else:
            count_result = await db.execute(
                select(func.count(Activity.id)).where(Activity.direction_hash.is_(None))
            )
        total_count = count_result.scalar() or 0

        logger.info(f"Found {total_count} activities to process {'(force mode)' if force else 'without direction_hash'}")

        if total_count == 0:
            return 0, 0

        processed = 0
        updated = 0
        offset = 0

        while offset < total_count:
            # Fetch batch of activities
            query = select(Activity).order_by(Activity.started_at).offset(offset).limit(batch_size)
            if not force:
                query = query.where(Activity.direction_hash.is_(None))
            
            result = await db.execute(query)
            activities = result.scalars().all()

            if not activities:
                break

            for activity in activities:
                processed += 1

                # Load GPS records for this activity
                records_result = await db.execute(
                    select(Record.lat, Record.lon, Record.distance_m)
                    .where(Record.activity_id == activity.id)
                    .where(Record.lat.isnot(None))
                    .where(Record.lon.isnot(None))
                    .order_by(Record.timestamp)
                    .limit(200)  # Only need first ~200 points for direction hash
                )
                records = records_result.all()

                if len(records) < 10:
                    logger.debug(f"Activity {activity.id}: insufficient GPS data ({len(records)} points)")
                    continue

                # Convert to format expected by compute_direction_hash
                gps_points = [(r.lat, r.lon, r.distance_m) for r in records]

                # Compute direction hash
                direction_hash = compute_direction_hash(gps_points)

                if direction_hash:
                    activity.direction_hash = direction_hash
                    updated += 1
                    logger.debug(f"Activity {activity.id}: computed hash {direction_hash[:8]}...")
                else:
                    logger.debug(f"Activity {activity.id}: could not compute hash")

            if not dry_run:
                await db.commit()
                logger.info(f"Committed batch: {processed}/{total_count} processed, {updated} updated")
            else:
                logger.info(f"[DRY RUN] Batch: {processed}/{total_count} processed, {updated} would be updated")
                await db.rollback()

            offset += batch_size

        return processed, updated


async def main():
    parser = argparse.ArgumentParser(description="Backfill direction_hash for existing activities")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of activities to process per batch (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't commit changes, just show what would be done",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute hashes for all activities, not just those missing hashes",
    )
    args = parser.parse_args()

    logger.info(f"Starting backfill (batch_size={args.batch_size}, dry_run={args.dry_run})")

    processed, updated = await backfill_direction_hashes(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        force=args.force,
    )

    logger.info(f"Backfill complete: {processed} activities processed, {updated} updated")


if __name__ == "__main__":
    asyncio.run(main())
