"""
FitnessModelUpdater use case — recompute the CP model and store a snapshot.

Loads all of a user's activities with peak-power data, fits the critical-power
model, writes a FitnessHistory row, and creates an FTP-divergence notification
if the fitted CP diverges from the user's current FTP by >5%.

This collapses the four duplicated copies of this sequence that lived in
``ingest._update_fitness_model``, ``ingest._update_fitness_model_batch``, and
``activity_pipeline.ActivityPipeline._update_fitness_model`` (see #307/#325).
"""

import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.fitness import fit_cp_model
from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower, FitnessHistory, Notification
from trainingdash.repositories.postgres.threshold_repo import PostgresThresholdRepo


class FitnessModelUpdater:
    """Recompute and store the user's fitness model (CP model + snapshot)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(self, user_id: int, activity_count: int | None = None) -> None:
        """Recompute the fitness model for ``user_id`` and store the snapshot.

        Flushes but does not commit — the caller owns the transaction. This
        composes inside the activity pipeline's single-transaction flow and
        inside worker jobs that commit at the end.

        Pass ``activity_count`` (the number of activities in a batch import)
        to produce a batch-summary FTP-divergence notification (with
        ``batch_import: True`` and ``activity_count`` in the payload, and
        any existing pending FTP notification replaced). Omit it for the
        single-ingest notification shape (dedupe-by-update).
        """
        # Load all activities with peaks for this user
        result = await self._db.execute(
            select(Activity).where(Activity.user_id == user_id).order_by(Activity.started_at.desc())
        )
        activities = result.scalars().all()

        if not activities:
            return

        # Load peaks for all activities
        activity_ids = [a.id for a in activities]
        result = await self._db.execute(
            select(ActivityPeakPower).where(ActivityPeakPower.activity_id.in_(activity_ids))
        )
        all_peaks = result.scalars().all()

        # Group peaks by activity
        peaks_by_activity: dict[int, dict[int, int]] = {}
        for p in all_peaks:
            peaks_by_activity.setdefault(p.activity_id, {})[p.duration_seconds] = p.watts

        # Build lists for model fitting
        peak_powers = []
        activity_dates = []
        for a in activities:
            if a.id in peaks_by_activity:
                peak_powers.append(peaks_by_activity[a.id])
                activity_dates.append(a.started_at)

        if not peak_powers:
            return

        # Fit the model
        model = fit_cp_model(peak_powers, activity_dates)
        if model is None:
            return

        # Store new fitness snapshot
        fitness = FitnessHistory(
            user_id=user_id,
            computed_at=datetime.now(UTC).replace(tzinfo=None),
            pp_watts=model["pp_watts"],
            w_prime_joules=model["w_prime_joules"],
            cp_watts=model["cp_watts"],
        )
        self._db.add(fitness)
        await self._db.flush()

        # Check if CP diverges from current FTP and create notification
        await self._check_ftp_notification(user_id, model["cp_watts"], activity_count)

    async def _check_ftp_notification(self, user_id: int, cp_watts: int, activity_count: int | None = None) -> None:
        """Create/update an FTP-divergence notification if CP diverges >5% from FTP.

        When ``activity_count`` is set, produces a batch-summary notification
        (replaces any existing pending FTP notification; payload carries
        ``batch_import: True`` and ``activity_count``). Otherwise dedupes by
        updating an existing pending notification in place.
        """
        current_ftp = (await PostgresThresholdRepo(self._db).get_for_date(user_id, date.today())).ftp_watts

        if current_ftp is None:
            return

        ratio = cp_watts / current_ftp
        if 0.95 <= ratio <= 1.05:
            return

        if activity_count is not None:
            message = (
                f"After importing {activity_count} activities, your fitness model "
                f"suggests updating your FTP from {current_ftp}W to {cp_watts}W"
            )
            payload = json.dumps(
                {
                    "current_ftp": current_ftp,
                    "suggested_ftp": cp_watts,
                    "divergence_pct": round((ratio - 1) * 100, 1),
                    "batch_import": True,
                    "activity_count": activity_count,
                }
            )
            # Batch mode: replace any existing pending FTP notifications
            result = await self._db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.type == "ftp_suggestion",
                    Notification.status == "pending",
                )
            )
            for n in result.scalars().all():
                await self._db.delete(n)
            await self._db.flush()
            self._db.add(
                Notification(
                    user_id=user_id,
                    type="ftp_suggestion",
                    message=message,
                    payload=payload,
                    status="pending",
                )
            )
            await self._db.flush()
            return

        # Single-ingest mode: dedupe by updating an existing pending notification
        result = await self._db.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.type == "ftp_suggestion",
                Notification.status == "pending",
            )
        )
        existing = result.scalar_one_or_none()

        message = f"Your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W"
        payload = json.dumps(
            {
                "current_ftp": current_ftp,
                "suggested_ftp": cp_watts,
                "divergence_pct": round((ratio - 1) * 100, 1),
            }
        )

        if existing is not None:
            existing.message = message
            existing.payload = payload
            await self._db.flush()
            return

        self._db.add(
            Notification(
                user_id=user_id,
                type="ftp_suggestion",
                message=message,
                payload=payload,
                status="pending",
            )
        )
        await self._db.flush()
