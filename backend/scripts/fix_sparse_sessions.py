#!/usr/bin/env python3
"""
Fix activities affected by the sparse-session-message bug (Karoo-via-Xert).

Some FIT files carry session messages that are missing summary fields
(no total_distance, avg/max speed, ascent, HR, or power). The ingest code
treated those missing fields as literal zeros and stored them, even though
the activity's records held complete data.

This script re-parses each affected activity's raw_fit with the fixed
parser (which falls back to record-derived values) and updates the stored
summary columns. Only columns that contradict the re-parsed values are
touched; everything else stays as-is.

Usage:
    python scripts/fix_sparse_sessions.py [--dry-run] [--activity-id UUID] [--all]

Options:
    --dry-run       Show what would be updated without making changes
    --activity-id   Fix a specific activity by UUID
    --all           Find and fix all activities whose stored summary
                    contradicts their records

Affected activities are detected by comparing stored summary values against
the records table: e.g. total_distance_m = 0 while records show >100m, or
avg_hr_bpm IS NULL while records contain HR samples.
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

from trainingdash.ingest import parse_records
from trainingdash.init_db import async_session
from trainingdash.repositories.postgres.models import Activity, Record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Summary columns to repair (they map 1:1 to parse_records keys), each with
# the record field that proves the stored zero/NULL is broken. `positive`
# means the record field must have non-zero samples (e.g. HR of 0 means
# "no reading", not "athlete flatlined").
# Fields intentionally NOT repaired here:
# - moving/elapsed/timer times: handled by fix_moving_time.py, and the
#   Karoo session messages did carry total_elapsed_time/total_timer_time
# - np_power_w, tss, training_load, zones, wbal: computed by the pipeline
#   from records regardless of the session message, so they were never wrong
# - map_polyline, route_id, title: derived from records, not the session
REPAIRED_FIELDS: dict[str, tuple[str, bool]] = {
    "total_distance_m": ("distance_m", True),
    "elevation_gain_m": ("altitude_m", False),
    "elevation_loss_m": ("altitude_m", False),
    "min_altitude_m": ("altitude_m", False),
    "max_altitude_m": ("altitude_m", False),
    "max_grade_pct": ("altitude_m", False),
    "avg_speed_mps": ("speed_mps", False),
    "avg_speed_moving_mps": ("speed_mps", False),
    "max_speed_mps": ("speed_mps", False),
    "avg_hr_bpm": ("hr_bpm", True),
    "max_hr_bpm": ("hr_bpm", True),
    "avg_power_w": ("power_w", False),
    "max_power_w": ("power_w", True),
    "avg_cadence_rpm": ("cadence_rpm", False),
    "avg_cadence_pedaling_rpm": ("cadence_rpm", True),
    "max_cadence_rpm": ("cadence_rpm", True),
    "avg_temperature_c": ("temperature_c", False),
    "min_temperature_c": ("temperature_c", False),
    "max_temperature_c": ("temperature_c", False),
}

# Thresholds used to decide whether a stored value is "wrong enough" to
# repair. Small differences between session-summary values and
# record-derived values are normal (devices compute them differently), so
# we only repair when the stored value is clearly broken.
RECORD_MIN_SAMPLES = 10


def _has_enough_samples(records: list[dict], key: str, positive: bool = False) -> bool:
    """True if records contain enough non-null samples of a field."""
    values = [r.get(key) for r in records if r.get(key) is not None]
    if positive:
        values = [v for v in values if v > 0]
    return len(values) >= RECORD_MIN_SAMPLES


def _needs_repair(activity: Activity, parsed: dict) -> list[str]:
    """
    Return the list of fields whose stored value is clearly broken.

    A value is broken when it is zero/NULL while the records (or the
    re-parsed summary) contain real data for the same field. Non-zero
    stored values are never overwritten — the device may legitimately
    disagree slightly with a record-derived recomputation.
    """
    fields = []

    for column, (record_key, positive) in REPAIRED_FIELDS.items():
        stored = getattr(activity, column)
        new = parsed.get(column)

        if new is None:
            continue  # nothing to repair from

        if stored is None or stored == 0:
            # Records must actually contain data for this field, otherwise
            # zero/NULL is the honest value.
            if _has_enough_samples(parsed["records"], record_key, positive=positive):
                fields.append(column)

    return fields


async def fix_activity(db: AsyncSession, activity: Activity, dry_run: bool) -> bool:
    """Re-parse raw_fit and repair broken summary columns."""
    if activity.raw_fit is None:
        logger.warning(f"Activity {activity.id} has no raw_fit data; cannot repair")
        return False

    try:
        parsed = parse_records(activity.raw_fit)
    except Exception as e:
        logger.error(f"Failed to parse raw_fit for {activity.id}: {e}")
        return False

    fields = _needs_repair(activity, parsed)
    if not fields:
        logger.info(f"Activity {activity.id} ({activity.title}): nothing to repair")
        return False

    logger.info(f"Activity {activity.id} ({activity.title}):")
    for column in fields:
        old = getattr(activity, column)
        new = parsed.get(column)
        logger.info(f"  {column}: {old!r} -> {new!r}")
        if not dry_run:
            setattr(activity, column, new)

    return True


async def find_affected_activities(db: AsyncSession) -> list[Activity]:
    """Find activities whose stored summary contradicts their records.

    A SQL pre-filter for the common breakage signatures; the Python-side
    _needs_repair() makes the final, finer-grained call per field.
    """
    signatures = [
        (Activity.total_distance_m == 0, Record.distance_m > 100),
        (Activity.avg_speed_mps == 0, Record.speed_mps > 1),
        (Activity.max_speed_mps == 0, Record.speed_mps > 1),
        (Activity.elevation_gain_m == 0, Record.altitude_m.isnot(None)),
        (Activity.avg_hr_bpm.is_(None), Record.hr_bpm > 0),
        (Activity.avg_power_w.is_(None), Record.power_w > 0),
    ]

    # Run each signature query separately and dedupe in Python — cleaner
    # than a SQL UNION, whose result rows don't map back to Activity entities.
    seen: dict = {}
    for broken, record_evidence in signatures:
        query = (
            select(Activity)
            .where(
                Activity.raw_fit.isnot(None),
                broken,
                Activity.id.in_(select(Record.activity_id).where(record_evidence).scalar_subquery()),
            )
            .order_by(Activity.started_at)
        )
        result = await db.execute(query)
        for activity in result.scalars().all():
            seen[activity.id] = activity

    return sorted(seen.values(), key=lambda a: a.started_at)


async def run(dry_run: bool, activity_id: UUID | None, fix_all: bool) -> int:
    """Returns the number of activities repaired (or that would be).

    Returns -1 if the requested activity does not exist.
    """
    async with async_session() as db:
        if activity_id is not None:
            result = await db.execute(select(Activity).where(Activity.id == activity_id))
            activities = [a for a in result.scalars().all() if a is not None]
            if not activities:
                logger.error(f"Activity {activity_id} not found")
                return -1
        elif fix_all:
            activities = await find_affected_activities(db)
            logger.info(f"Found {len(activities)} candidate activities")
        else:
            return 0

        repaired = 0
        for activity in activities:
            if await fix_activity(db, activity, dry_run):
                repaired += 1

        if dry_run:
            logger.info(f"DRY RUN: would repair {repaired}/{len(activities)} activities")
        else:
            await db.commit()
            logger.info(f"Repaired {repaired}/{len(activities)} activities")

    return repaired


def main():
    parser = argparse.ArgumentParser(
        description="Fix activities with zeroed summaries from sparse FIT sessions",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--activity-id", type=str, help="Fix a specific activity by UUID")
    parser.add_argument("--all", action="store_true", help="Find and fix all affected activities")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")

    if args.activity_id:
        try:
            activity_uuid = UUID(args.activity_id)
        except ValueError:
            logger.error(f"Invalid UUID: {args.activity_id}")
            sys.exit(1)
        repaired = asyncio.run(run(args.dry_run, activity_uuid, fix_all=False))
        if repaired < 0:
            sys.exit(1)
    elif args.all:
        asyncio.run(run(args.dry_run, None, fix_all=True))
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
