"""
HourlyImportScheduler use case — enqueue import jobs for users whose sync_hour matches.

Cron job: runs hourly. Garmin imports are enqueued immediately (at :00); Xert
imports are deferred by 15 minutes to stagger API calls.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.jobs import enqueue_import_garmin_job, enqueue_import_xert_job
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import GarminCredentials, User, XertCredentials

logger = logging.getLogger(__name__)


class HourlyImportScheduler:
    """Enqueue import jobs for users whose sync_hour matches the current hour."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._event_repo = PostgresEventRepo(db)

    async def execute(self) -> dict:
        current_hour = datetime.now(UTC).hour
        logger.info(f"HourlyImportScheduler: running for hour {current_hour}")

        # Find users with this sync_hour who have Garmin credentials with import enabled
        garmin_result = await self._db.execute(
            select(GarminCredentials.user_id)
            .join(User, User.id == GarminCredentials.user_id)
            .where(User.sync_hour == current_hour)
            .where(GarminCredentials.sync_enabled == True)
        )
        garmin_user_ids = garmin_result.scalars().all()

        # Find users with this sync_hour who have Xert credentials with import enabled
        xert_result = await self._db.execute(
            select(XertCredentials.user_id)
            .join(User, User.id == XertCredentials.user_id)
            .where(User.sync_hour == current_hour)
            .where(XertCredentials.sync_enabled == True)
        )
        xert_user_ids = xert_result.scalars().all()

        if not garmin_user_ids and not xert_user_ids:
            logger.info(f"HourlyImportScheduler: no users scheduled for hour {current_hour}")
            return {"success": True, "garmin_queued": 0, "xert_queued": 0}

        # Lost-tick safeguard (ADR 0006, decision 3): a scheduled user whose
        # last_synced_at is >25h stale likely missed ticks while the worker was
        # down — SAQ cron never back-runs them. The next healthy tick's import
        # range derives from last_synced_at, so data converges; this event makes
        # the loss visible to admins (ADR 0007 dead-letter/enqueue-failure feed).
        hour_bucket = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        scheduled_user_ids = [*garmin_user_ids, *xert_user_ids]
        stale_result = await self._db.execute(
            select(GarminCredentials.user_id, GarminCredentials.last_synced_at).where(
                GarminCredentials.user_id.in_(scheduled_user_ids)
            )
        )
        await self._log_lost_ticks(stale_result)

        # Enqueue Garmin imports immediately — hour-bucketed key dedupes a
        # retried scheduler tick at enqueue time (ADR 0006, decision 1)
        for user_id in garmin_user_ids:
            await enqueue_import_garmin_job(user_id, key=f"import:garmin:{user_id}:{hour_bucket}")
            logger.info(f"HourlyImportScheduler: enqueued Garmin import for user {user_id}")

        # Enqueue Xert imports with 15 minute delay to stagger API calls —
        # hour-bucketed key dedupes a retried scheduler tick (ADR 0006, decision 1)
        defer_until = time.time() + (15 * 60)
        for user_id in xert_user_ids:
            await enqueue_import_xert_job(user_id, scheduled=defer_until, key=f"import:xert:{user_id}:{hour_bucket}")
            logger.info(f"HourlyImportScheduler: enqueued Xert import for user {user_id} (deferred 15min)")

        logger.info(f"HourlyImportScheduler: queued {len(garmin_user_ids)} Garmin, {len(xert_user_ids)} Xert imports")

        # Emit scheduler.triggered event
        await self._event_repo.log(
            event_type=EventType.SCHEDULER_TRIGGERED.value,
            outcome=EventOutcome.INFO.value,
            user_id=None,
            payload={
                "hour": current_hour,
                "garmin_queued": len(garmin_user_ids),
                "xert_queued": len(xert_user_ids),
            },
        )
        await self._db.commit()

        return {"success": True, "garmin_queued": len(garmin_user_ids), "xert_queued": len(xert_user_ids)}

    async def _log_lost_ticks(self, garmin_stale_result) -> None:
        """Write sync.lost_tick events for scheduled users whose Garmin last_synced_at is >25h stale."""
        stale_threshold = datetime.now(UTC) - timedelta(hours=25)
        rows = garmin_stale_result.all()
        for user_id, last_synced_at in rows:
            if last_synced_at is None or last_synced_at.replace(tzinfo=UTC) < stale_threshold:
                try:
                    await self._event_repo.log(
                        event_type=EventType.SYNC_LOST_TICK.value,
                        outcome=EventOutcome.FAILURE.value,
                        user_id=user_id,
                        payload={
                            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
                            "reason": "scheduled user missed ticks (worker down or enqueue lost)",
                        },
                    )
                except Exception:
                    logger.exception("Failed to log sync.lost_tick event for user %s", user_id)
