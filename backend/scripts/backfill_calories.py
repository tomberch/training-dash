#!/usr/bin/env python3
"""
Backfill calories for existing activities.

This script re-parses raw FIT files to populate the calories and calories_source
fields added in migration 032:

- calories: Integer kcal value
- calories_source: 'device' (from FIT session) or 'computed_power' (kJ from power)

Uses the same resolution logic as ingest: device-reported total_calories from
the FIT session message takes precedence; otherwise computes from power work
(kJ ≈ kcal approximation).

Usage:
    python scripts/backfill_calories.py [--dry-run] [--user-id USER_ID] [--batch-size N] [--force]

Options:
    --dry-run       Show what would be updated without making changes
    --user-id       Only process activities for a specific user
    --batch-size    Number of activities to process per batch (default: 100)
    --force         Re-compute calories even if already set
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

from trainingdash.domain.calories import resolve_calories
from trainingdash.ingest import parse_records
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def backfill_activity(
    db: AsyncSession,
    activity: Activity,
    dry_run: bool,
    force: bool = False,
) -> bool:
    """
    Backfill calories for a single activity.

    Returns True if activity was updated, False if skipped.
    """
    if activity.raw_fit is None:
        logger.debug(f"Skipping {activity.id}: no raw_fit data")
        return False

    # Skip if already has calories (unless force mode)
    if activity.calories is not None and not force:
        logger.debug(f"Skipping {activity.id}: calories already set ({activity.calories})")
        return False

    try:
        # Re-parse the FIT file
        parsed = parse_records(activity.raw_fit)

        # Get session calories (device-reported) and records for power computation
        session_calories = parsed.get("session_calories")
        records = parsed.get("records", [])

        # Resolve calories using the same logic as ingest
        calories, source = resolve_calories(session_calories, records)

        if calories is None:
            logger.debug(f"Skipping {activity.id}: no calories data (no device value, no power)")
            return False

        if dry_run:
            logger.info(f"[DRY RUN] Would update {activity.id}: calories={calories}, source={source}")
        else:
            activity.calories = calories
            activity.calories_source = source
            logger.info(f"Updated {activity.id}: calories={calories}, source={source}")

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
    Backfill calories for all activities.

    Returns (total, updated, skipped) counts.
    """
    async with async_session() as db:
        # Build base query for activities needing backfill
        base_filter = Activity.raw_fit.isnot(None)
        if not force:
            # Only process activities without calories
            base_filter = base_filter & Activity.calories.is_(None)
        if user_id:
            base_filter = base_filter & (Activity.user_id == user_id)

        # Count total activities to process
        count_query = select(func.count(Activity.id)).where(base_filter)
        result = await db.execute(count_query)
        total = result.scalar() or 0

        logger.info(f"Found {total} activities to process")

        if total == 0:
            return 0, 0, 0

        updated = 0
        skipped = 0
        offset = 0

        while True:
            # Fetch batch
            query = select(Activity).where(base_filter).order_by(Activity.started_at).offset(offset).limit(batch_size)

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
            processed = min(offset, total)
            logger.info(f"Progress: {processed}/{total} ({updated} updated, {skipped} skipped)")

        return total, updated, skipped


def main():
    """CLI entrypoint for calories backfill."""
    parser = argparse.ArgumentParser(description="Backfill calories for existing activities")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        help="Only process activities for a specific user",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of activities to process per batch",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-compute calories even if already set",
    )

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
