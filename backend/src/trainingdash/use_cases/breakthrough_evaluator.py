"""
BreakthroughEvaluator use case — re-evaluate is_breakthrough flags.

Walks all of a user's activities chronologically, recomputing which are
breakthroughs based on all-time-best peak powers. Mutates ``Activity.is_breakthrough``
in place and flushes.

This collapses the two duplicated copies of this sequence that lived inline in
``finalize_batch_import`` (ingest.py:617-639) and ``worker.recalculate_after_delete_job``
(lines 160-194). See #307/#325.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.fitness import detect_breakthrough, get_all_time_bests
from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower


class BreakthroughEvaluator:
    """Re-evaluate ``is_breakthrough`` flags for all of a user's activities."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(self, user_id: int) -> None:
        """Walk activities chronologically and recompute breakthrough flags.

        Flushes but does not commit — the caller owns the transaction.
        """
        # Load activities chronologically
        result = await self._db.execute(
            select(Activity)
            .where(Activity.user_id == user_id)
            .order_by(Activity.started_at.asc())
        )
        activities = result.scalars().all()

        if not activities:
            return

        # Load all peak powers for this user's activities
        activity_ids = [a.id for a in activities]
        result = await self._db.execute(
            select(ActivityPeakPower).where(
                ActivityPeakPower.activity_id.in_(activity_ids)
            )
        )
        all_peaks = result.scalars().all()

        peaks_by_activity: dict[int, dict[int, int]] = {}
        for p in all_peaks:
            peaks_by_activity.setdefault(p.activity_id, {})[p.duration_seconds] = p.watts

        # Walk chronologically, re-evaluating breakthroughs
        seen_peaks: list[dict[int, int]] = []
        for activity in activities:
            activity_peaks = peaks_by_activity.get(activity.id, {})
            all_time_bests = get_all_time_bests(seen_peaks)
            is_bt = detect_breakthrough(activity_peaks, all_time_bests) if activity_peaks else False
            if activity.is_breakthrough != is_bt:
                activity.is_breakthrough = is_bt
            if activity_peaks:
                seen_peaks.append(activity_peaks)

        await self._db.flush()