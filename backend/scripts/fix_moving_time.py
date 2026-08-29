#!/usr/bin/env python3
"""
Fix moving_time_s and avg_speed_moving_mps for activities affected by the
smart-recording bug (where each record was counted as 1 second regardless
of actual timestamp intervals).

This script recomputes moving_time_s from the activity's records using the
corrected _compute_moving_time function, then updates avg_speed_moving_mps.

Usage:
    python scripts/fix_moving_time.py [--dry-run] [--activity-id UUID] [--all]

Options:
    --dry-run       Show what would be updated without making changes
    --activity-id   Fix a specific activity by UUID
    --all           Fix all activities (recompute from raw_fit or records)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

# Add backend/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.ingest import _compute_moving_time, parse_records
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def fix_activity_from_fit(db: AsyncSession, activity: Activity, dry_run: bool) -> bool:
    """Fix moving time by re-parsing the raw FIT file."""
    if activity.raw_fit is None:
        logger.warning(f"Activity {activity.id} has no raw_fit data")
        return False

    try:
        parsed = parse_records(activity.raw_fit)
        new_moving_time = parsed.get("moving_time_s")

        if new_moving_time is None:
            logger.warning(f"Activity {activity.id}: could not compute moving_time from FIT")
            return False

        # Compute new avg_speed_moving_mps
        new_avg_speed_moving = None
        if new_moving_time > 0 and activity.total_distance_m > 0:
            new_avg_speed_moving = round(activity.total_distance_m / new_moving_time, 3)

        logger.info(
            f"Activity {activity.id} ({activity.title}):\n"
            f"  moving_time_s: {activity.moving_time_s} -> {new_moving_time}\n"
            f"  avg_speed_moving_mps: {activity.avg_speed_moving_mps} -> {new_avg_speed_moving}"
        )

        if not dry_run:
            activity.moving_time_s = new_moving_time
            activity.avg_speed_moving_mps = new_avg_speed_moving

        return True

    except Exception as e:
        logger.error(f"Failed to process activity {activity.id}: {e}")
        return False


async def fix_activity_from_records(db: AsyncSession, activity: Activity, dry_run: bool) -> bool:
    """Fix moving time by loading records from the database."""
    result = await db.execute(select(Record).where(Record.activity_id == activity.id).order_by(Record.timestamp))
    records = result.scalars().all()

    if not records:
        logger.warning(f"Activity {activity.id} has no records")
        return False

    # Convert ORM records to dicts for _compute_moving_time
    record_dicts = [{"timestamp": r.timestamp, "speed_mps": r.speed_mps} for r in records]

    new_moving_time = _compute_moving_time(record_dicts)

    # Compute new avg_speed_moving_mps
    new_avg_speed_moving = None
    if new_moving_time > 0 and activity.total_distance_m > 0:
        new_avg_speed_moving = round(activity.total_distance_m / new_moving_time, 3)

    logger.info(
        f"Activity {activity.id} ({activity.title}):\n"
        f"  moving_time_s: {activity.moving_time_s} -> {new_moving_time}\n"
        f"  avg_speed_moving_mps: {activity.avg_speed_moving_mps} -> {new_avg_speed_moving}"
    )

    if not dry_run:
        activity.moving_time_s = new_moving_time
        activity.avg_speed_moving_mps = new_avg_speed_moving

    return True


async def fix_single_activity(activity_id: UUID, dry_run: bool) -> bool:
    """Fix a single activity by ID."""
    async with async_session() as db:
        result = await db.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one_or_none()

        if activity is None:
            logger.error(f"Activity {activity_id} not found")
            return False

        # Prefer raw_fit if available, otherwise use records from DB
        if activity.raw_fit:
            success = await fix_activity_from_fit(db, activity, dry_run)
        else:
            success = await fix_activity_from_records(db, activity, dry_run)

        if success and not dry_run:
            await db.commit()

        return success


async def fix_all_activities(dry_run: bool) -> tuple[int, int]:
    """Fix all activities. Returns (total, fixed) counts."""
    async with async_session() as db:
        result = await db.execute(select(Activity).order_by(Activity.started_at))
        activities = result.scalars().all()

        total = len(activities)
        fixed = 0

        for activity in activities:
            if activity.raw_fit:
                success = await fix_activity_from_fit(db, activity, dry_run)
            else:
                success = await fix_activity_from_records(db, activity, dry_run)

            if success:
                fixed += 1

        if not dry_run:
            await db.commit()

        return total, fixed


def main():
    parser = argparse.ArgumentParser(description="Fix moving_time_s for smart-recording bug")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--activity-id", type=str, help="Fix a specific activity by UUID")
    parser.add_argument("--all", action="store_true", help="Fix all activities")

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    if args.activity_id:
        try:
            activity_uuid = UUID(args.activity_id)
        except ValueError:
            logger.error(f"Invalid UUID: {args.activity_id}")
            sys.exit(1)

        success = asyncio.run(fix_single_activity(activity_uuid, args.dry_run))
        sys.exit(0 if success else 1)

    elif args.all:
        total, fixed = asyncio.run(fix_all_activities(args.dry_run))
        logger.info(f"Fixed {fixed}/{total} activities")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
