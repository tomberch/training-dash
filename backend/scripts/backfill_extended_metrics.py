#!/usr/bin/env python3
"""
Backfill extended metrics for existing activities.

This script re-parses raw FIT files stored in activities to populate the new
extended metrics fields added in migration 021 and 022:

- timer_time_s
- moving_time_s (recomputed from records when FIT lacks total_moving_time)
- elevation_loss_m, min_altitude_m, max_altitude_m, max_grade_pct
- avg_speed_moving_mps
- max_power_w
- avg_cadence_rpm (overall average including zeros)
- avg_cadence_pedaling_rpm (average only when pedaling)
- max_cadence_rpm
- avg_temperature_c, min_temperature_c, max_temperature_c

Usage:
    python scripts/backfill_extended_metrics.py [--dry-run] [--user-id USER_ID] [--batch-size N] [--force]

Options:
    --dry-run       Show what would be updated without making changes
    --user-id       Only process activities for a specific user
    --batch-size    Number of activities to process per batch (default: 100)
    --force         Re-compute all metrics even if already set (useful for fixing bugs)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add backend/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.ingest import parse_records
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_activity(db: AsyncSession, activity: Activity, dry_run: bool, force: bool = False) -> bool:
    """
    Backfill extended metrics for a single activity.

    Returns True if activity was updated, False if skipped.
    """
    if activity.raw_fit is None:
        logger.debug(f"Skipping {activity.id}: no raw_fit data")
        return False

    try:
        # Re-parse the FIT file
        parsed = parse_records(activity.raw_fit)

        # Check if we got new data
        updates = {}

        # Time metrics - always recompute moving_time (fixes bug where we used timer_time)
        if parsed.get("timer_time_s") is not None and (activity.timer_time_s is None or force):
            updates["timer_time_s"] = parsed["timer_time_s"]

        # Always update moving_time_s if the new value differs (fixes the timer_time bug)
        if parsed.get("moving_time_s") and parsed["moving_time_s"] != activity.moving_time_s:
            updates["moving_time_s"] = parsed["moving_time_s"]

        # Elevation metrics
        if parsed.get("elevation_loss_m") is not None and (activity.elevation_loss_m is None or force):
            updates["elevation_loss_m"] = parsed["elevation_loss_m"]
        if parsed.get("min_altitude_m") is not None and (activity.min_altitude_m is None or force):
            updates["min_altitude_m"] = parsed["min_altitude_m"]
        if parsed.get("max_altitude_m") is not None and (activity.max_altitude_m is None or force):
            updates["max_altitude_m"] = parsed["max_altitude_m"]
        if parsed.get("max_grade_pct") is not None and (activity.max_grade_pct is None or force):
            updates["max_grade_pct"] = parsed["max_grade_pct"]

        # Speed metrics
        if parsed.get("avg_speed_moving_mps") is not None and (activity.avg_speed_moving_mps is None or force):
            updates["avg_speed_moving_mps"] = parsed["avg_speed_moving_mps"]

        # Power metrics
        if parsed.get("max_power_w") is not None and (activity.max_power_w is None or force):
            updates["max_power_w"] = parsed["max_power_w"]

        # Cadence metrics - always recompute (fixes bug where avg was same as pedaling avg)
        if parsed.get("avg_cadence_rpm") is not None:
            if (
                activity.avg_cadence_rpm is None
                or force
                or activity.avg_cadence_rpm == activity.avg_cadence_pedaling_rpm
            ):
                updates["avg_cadence_rpm"] = parsed["avg_cadence_rpm"]
        if parsed.get("avg_cadence_pedaling_rpm") is not None:
            if activity.avg_cadence_pedaling_rpm is None or force:
                updates["avg_cadence_pedaling_rpm"] = parsed["avg_cadence_pedaling_rpm"]
        if parsed.get("max_cadence_rpm") is not None and (activity.max_cadence_rpm is None or force):
            updates["max_cadence_rpm"] = parsed["max_cadence_rpm"]

        # Temperature metrics
        if parsed.get("avg_temperature_c") is not None and (activity.avg_temperature_c is None or force):
            updates["avg_temperature_c"] = parsed["avg_temperature_c"]
        if parsed.get("min_temperature_c") is not None and (activity.min_temperature_c is None or force):
            updates["min_temperature_c"] = parsed["min_temperature_c"]
        if parsed.get("max_temperature_c") is not None and (activity.max_temperature_c is None or force):
            updates["max_temperature_c"] = parsed["max_temperature_c"]

        if not updates:
            logger.debug(f"Skipping {activity.id}: no new data to update")
            return False

        if dry_run:
            logger.info(f"[DRY RUN] Would update {activity.id}: {list(updates.keys())}")
        else:
            for key, value in updates.items():
                setattr(activity, key, value)
            logger.info(f"Updated {activity.id}: {list(updates.keys())}")

        return True

    except Exception as e:
        logger.warning(f"Failed to process {activity.id}: {e}")
        return False


async def backfill_all(
    dry_run: bool = False,
    user_id: int | None = None,
    batch_size: int = 100,
    force: bool = False,
) -> tuple[int, int, int]:
    """
    Backfill extended metrics for all activities.

    Returns (total, updated, skipped) counts.
    """
    async with async_session() as db:
        # Count total activities
        query = select(func.count(Activity.id))
        if user_id:
            query = query.where(Activity.user_id == user_id)
        result = await db.execute(query)
        total = result.scalar() or 0

        logger.info(f"Found {total} activities to process")

        updated = 0
        skipped = 0
        offset = 0

        while offset < total:
            # Fetch batch
            query = (
                select(Activity)
                .where(Activity.raw_fit.isnot(None))
                .order_by(Activity.started_at)
                .offset(offset)
                .limit(batch_size)
            )
            if user_id:
                query = query.where(Activity.user_id == user_id)

            result = await db.execute(query)
            activities = result.scalars().all()

            if not activities:
                break

            for activity in activities:
                if await backfill_activity(db, activity, dry_run, force):
                    updated += 1
                else:
                    skipped += 1

            if not dry_run:
                await db.commit()

            offset += batch_size
            logger.info(f"Progress: {offset}/{total} ({updated} updated, {skipped} skipped)")

        return total, updated, skipped


def main():
    parser = argparse.ArgumentParser(description="Backfill extended metrics for existing activities")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without making changes")
    parser.add_argument("--user-id", type=int, help="Only process activities for a specific user")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of activities to process per batch")
    parser.add_argument("--force", action="store_true", help="Re-compute all metrics even if already set")

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")
    if args.force:
        logger.info("FORCE MODE - will overwrite existing values")

    total, updated, skipped = asyncio.run(
        backfill_all(
            dry_run=args.dry_run,
            user_id=args.user_id,
            batch_size=args.batch_size,
            force=args.force,
        )
    )

    logger.info(f"Backfill complete: {total} total, {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    main()
