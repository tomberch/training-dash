#!/usr/bin/env python3
"""One-off data repair: merge duplicate suggested climb segments.

The suggestion dedup used strict endpoint gates (is_same_segment: start
within 25m, end within 25m), but detected climb boundaries wobble between
rides — detectors start/extend the same climb metres apart or partway
down the descent. Result: one road could accumulate several suggested
segments, each with a low repetition_count, and none reached the
3-repetition visibility threshold.

This script clusters suggested segments by the same-road containment
criterion (describes_same_road — the fixed dedup) and, per cluster:
1. Keeps one canonical segment (the longest — best climb coverage).
2. Merges every duplicate's SegmentSuggestion rows into the canonical
   segment's suggestion: summed repetition_count, earliest first_ridden_at,
   latest last_ridden_at / expires_at.
3. Soft-deletes the duplicate segments (efforts, if any, are re-pointed).

Idempotent: after a merge, duplicates are soft-deleted, so re-running
finds nothing to merge.

Usage:
    docker exec traindash-dev-app-1 python scripts/merge_duplicate_suggestions.py [--dry-run]
"""

import argparse
import asyncio
import logging
import math
import os
from datetime import datetime

from geoalchemy2.shape import to_shape
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from trainingdash.domain.polyline import decode_polyline
from trainingdash.domain.segment_matching import describes_same_road

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Candidate pairs only need a spatial prefilter (like find_similar_suggested):
# start points within 100 m.
PREFILTER_RADIUS_DEG = 0.001


async def merge(db_url: str, dry_run: bool) -> None:
    from trainingdash.repositories.postgres.models import (
        Segment,
        SegmentEffort,
        SegmentSuggestion,
    )

    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            select(Segment).where(
                Segment.status == "suggested",
                Segment.deleted_at.is_(None),
            )
        )
        segments = list(result.scalars().all())
        logger.info(f"Loaded {len(segments)} suggested segments")

        # Load polylines once for clustering (keep encoded strings —
        # describes_same_road takes encoded polylines)
        paths = {}
        for seg in segments:
            try:
                pts = decode_polyline(seg.polyline)
                if len(pts) >= 2:
                    paths[seg.id] = seg.polyline
            except Exception:
                continue

        # Union-find clustering via pairwise containment within 100 m start radius
        by_id = {seg.id: seg for seg in segments if seg.id in paths}
        ids = list(paths.keys())
        parent = {i: i for i in ids}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        start_points = {}
        for seg_id, seg in by_id.items():
            shape = to_shape(seg.start_point)
            start_points[seg_id] = (shape.y, shape.x)

        for i, id_a in enumerate(ids):
            for id_b in ids[i + 1 :]:
                a, b = by_id[id_a], by_id[id_b]
                pa, pb = start_points[id_a], start_points[id_b]
                if _haversine(pa, pb) > 100.0:
                    continue
                if describes_same_road(
                    polyline=paths[id_a], other_polyline=paths[id_b]
                ):
                    union(id_a, id_b)

        clusters: dict[object, list] = {}
        for seg_id in ids:
            clusters.setdefault(find(seg_id), []).append(seg_id)
        dup_clusters = {root: members for root, members in clusters.items() if len(members) > 1}
        logger.info(f"Found {len(dup_clusters)} duplicate clusters")

        merged_suggestions = 0
        soft_deleted = 0

        for root, members in dup_clusters.items():
            # Keep the longest segment (most complete climb capture)
            keeper = max(members, key=lambda sid: by_id[sid].distance_m or 0)
            keeper_seg = by_id[keeper]

            suggestions = {}
            sugg_result = await session.execute(
                select(SegmentSuggestion).where(SegmentSuggestion.segment_id.in_(members))
            )
            for s in sugg_result.scalars().all():
                suggestions.setdefault(s.user_id, []).append(s)

            for user_id, user_suggs in suggestions.items():
                total = sum(s.repetition_count for s in user_suggs)
                keeper_sugg = next((s for s in user_suggs if s.segment_id == keeper), None)
                dup_suggs = [s for s in user_suggs if s.segment_id != keeper]

                if dry_run:
                    logger.info(
                        f"[dry-run] cluster keeper {keeper} would absorb "
                        f"{len(dup_suggs)} suggestions, repetition_count -> {total}"
                    )
                    continue

                if keeper_sugg is None:
                    first = min(s.first_ridden_at for s in user_suggs)
                    last = max(s.last_ridden_at for s in user_suggs)
                    expires = max(s.expires_at for s in user_suggs if s.expires_at)
                    keeper_sugg = SegmentSuggestion(
                        segment_id=keeper,
                        user_id=user_id,
                        repetition_count=0,
                        first_ridden_at=first,
                        last_ridden_at=last,
                        expires_at=expires,
                    )
                    session.add(keeper_sugg)
                else:
                    keeper_sugg.repetition_count = total
                    keeper_sugg.first_ridden_at = min(
                        s.first_ridden_at for s in user_suggs
                    )
                    keeper_sugg.last_ridden_at = max(
                        s.last_ridden_at for s in user_suggs
                    )
                    keeper_sugg.expires_at = max(
                        s.expires_at for s in user_suggs if s.expires_at is not None
                    ) if any(s.expires_at is not None for s in user_suggs) else None

                for dup in dup_suggs:
                    await session.delete(dup)
                    merged_suggestions += 1

            if dry_run:
                continue

            # Re-point any efforts to the keeper, then soft-delete duplicates
            for member in members:
                if member == keeper:
                    continue
                await session.execute(
                    SegmentEffort.__table__.update()
                    .where(SegmentEffort.segment_id == member)
                    .values(segment_id=keeper)
                )
                await session.execute(
                    Segment.__table__.update()
                    .where(Segment.id == member)
                    .values(deleted_at=__import__("datetime").datetime.now())
                )
                soft_deleted += 1

        if not dry_run:
            await session.commit()
        logger.info(
            f"Done: {merged_suggestions} suggestions merged, "
            f"{soft_deleted} segments soft-deleted{' (dry run)' if dry_run else ''}"
        )

    await engine.dispose()


def _haversine(p1, p2) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (*p1, *p2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(h))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://trainingdash:trainingdash@db:5432/trainingdash",
    )
    asyncio.run(merge(db_url, args.dry_run))


if __name__ == "__main__":
    main()