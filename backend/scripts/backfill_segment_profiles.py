#!/usr/bin/env python3
"""
Backfill elevation profiles for existing segments.

This script recomputes segment geometry from source activity records to populate
the new elevation_profile field and update max_grade_pct with the windowed algorithm.

Usage:
    python scripts/backfill_segment_profiles.py [--dry-run] [--batch-size N] [--segment-id UUID]

Options:
    --dry-run       Show what would be updated without making changes
    --batch-size    Number of segments to process per batch (default: 100)
    --segment-id    Only process a specific segment (useful for testing)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

# Add backend/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.segment_geometry import compute_segment_geometry
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Record, Segment, SegmentEffort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def find_segment_indices(
    db: AsyncSession,
    segment: Segment,
) -> tuple[int, int] | None:
    """
    Find start/end indices for a segment from its SegmentEffort records.

    Returns the indices from the first matching effort, or None if no effort found.
    """
    result = await db.execute(
        select(SegmentEffort)
        .where(SegmentEffort.segment_id == segment.id)
        .where(SegmentEffort.activity_id == segment.source_activity_id)
        .order_by(SegmentEffort.start_index)
        .limit(1)
    )
    effort = result.scalar_one_or_none()

    if effort:
        return (effort.start_index, effort.end_index)
    return None


async def load_activity_records(db: AsyncSession, activity_id: UUID) -> list[dict]:
    """Load activity records as dicts for domain functions."""
    result = await db.execute(
        select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
    )
    records = result.scalars().all()

    return [
        {
            "lat": r.lat,
            "lon": r.lon,
            "altitude_m": r.altitude_m,
            "distance_m": r.distance_m or 0.0,
        }
        for r in records
        if r.lat is not None and r.lon is not None
    ]


async def backfill_segment(
    db: AsyncSession,
    segment: Segment,
    dry_run: bool,
) -> bool:
    """
    Backfill elevation profile for a single segment.

    Returns True if segment was updated, False if skipped.
    """
    if segment.source_activity_id is None:
        logger.debug(f"Skipping {segment.id}: no source_activity_id")
        return False

    # Find indices from SegmentEffort
    indices = await find_segment_indices(db, segment)
    if indices is None:
        logger.warning(f"Skipping {segment.id}: no SegmentEffort found for source activity")
        return False

    start_index, end_index = indices

    # Load activity records
    records = await load_activity_records(db, segment.source_activity_id)
    if len(records) < 2:
        logger.warning(f"Skipping {segment.id}: source activity has insufficient records")
        return False

    if end_index >= len(records):
        logger.warning(
            f"Skipping {segment.id}: end_index {end_index} exceeds record count {len(records)}"
        )
        return False

    # Recompute geometry
    try:
        geometry = compute_segment_geometry(records, start_index, end_index)
    except ValueError as e:
        logger.warning(f"Skipping {segment.id}: geometry computation failed: {e}")
        return False

    # Build elevation_profile as list of dicts
    elevation_profile = [
        {
            "distance_m": ep.distance_m,
            "elevation_m": ep.elevation_m,
            "grade_pct": ep.grade_pct,
        }
        for ep in geometry.elevation_profile
    ]

    # Check what changed
    changes = []
    if segment.elevation_profile != elevation_profile:
        changes.append(f"elevation_profile: {len(segment.elevation_profile or [])} -> {len(elevation_profile)} points")
    if abs((segment.max_grade_pct or 0) - geometry.max_grade_pct) > 0.01:
        changes.append(f"max_grade_pct: {segment.max_grade_pct:.2f} -> {geometry.max_grade_pct:.2f}")
    if abs((segment.avg_grade_pct or 0) - geometry.avg_grade_pct) > 0.01:
        changes.append(f"avg_grade_pct: {segment.avg_grade_pct:.2f} -> {geometry.avg_grade_pct:.2f}")
    if abs((segment.elevation_gain_m or 0) - geometry.elevation_gain_m) > 0.1:
        changes.append(f"elevation_gain_m: {segment.elevation_gain_m:.1f} -> {geometry.elevation_gain_m:.1f}")
    if abs((segment.distance_m or 0) - geometry.distance_m) > 0.1:
        changes.append(f"distance_m: {segment.distance_m:.1f} -> {geometry.distance_m:.1f}")

    if not changes:
        logger.debug(f"Skipping {segment.id}: no changes needed")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Would update {segment.id} ({segment.name}): {', '.join(changes)}")
    else:
        segment.elevation_profile = elevation_profile
        segment.max_grade_pct = geometry.max_grade_pct
        segment.avg_grade_pct = geometry.avg_grade_pct
        segment.elevation_gain_m = geometry.elevation_gain_m
        segment.distance_m = geometry.distance_m
        logger.info(f"Updated {segment.id} ({segment.name}): {', '.join(changes)}")

    return True


async def backfill_all(
    dry_run: bool = False,
    batch_size: int = 100,
    segment_id: UUID | None = None,
) -> tuple[int, int, int]:
    """
    Backfill elevation profiles for all segments.

    Returns (total, updated, skipped) counts.
    """
    async with async_session() as db:
        # Build base query for segments with source_activity_id
        base_filter = [
            Segment.source_activity_id.isnot(None),
            Segment.deleted_at.is_(None),
        ]
        if segment_id:
            base_filter.append(Segment.id == segment_id)

        # Count total segments
        count_query = select(func.count(Segment.id)).where(*base_filter)
        result = await db.execute(count_query)
        total = result.scalar() or 0

        if segment_id and total == 0:
            logger.error(f"Segment {segment_id} not found or has no source_activity_id")
            return (0, 0, 0)

        logger.info(f"Found {total} segments to process")

        updated = 0
        skipped = 0
        offset = 0

        while offset < total:
            # Fetch batch
            query = (
                select(Segment)
                .where(*base_filter)
                .order_by(Segment.created_at)
                .offset(offset)
                .limit(batch_size)
            )

            result = await db.execute(query)
            segments = result.scalars().all()

            if not segments:
                break

            for segment in segments:
                if await backfill_segment(db, segment, dry_run):
                    updated += 1
                else:
                    skipped += 1

            if not dry_run:
                await db.commit()

            offset += batch_size
            logger.info(f"Progress: {min(offset, total)}/{total} ({updated} updated, {skipped} skipped)")

        return total, updated, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Backfill elevation profiles for existing segments"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of segments to process per batch (default: 100)",
    )
    parser.add_argument(
        "--segment-id",
        type=str,
        help="Only process a specific segment UUID",
    )

    args = parser.parse_args()

    segment_id = None
    if args.segment_id:
        try:
            segment_id = UUID(args.segment_id)
        except ValueError:
            logger.error(f"Invalid segment UUID: {args.segment_id}")
            sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    total, updated, skipped = asyncio.run(
        backfill_all(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            segment_id=segment_id,
        )
    )

    logger.info(f"Backfill complete: {total} total, {updated} updated, {skipped} skipped")


if __name__ == "__main__":
    main()
