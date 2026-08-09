"""
HourlySyncScheduler use case — enqueue sync jobs for users whose sync_hour matches.

Cron job: runs hourly. Garmin syncs are enqueued immediately (at :00); Xert
syncs are deferred by 15 minutes to stagger API calls.
"""

import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.jobs import enqueue_sync_garmin_job, enqueue_sync_xert_job
from trainingdash.repositories.postgres.models import GarminCredentials, User, XertCredentials

logger = logging.getLogger(__name__)


class HourlySyncScheduler:
    """Enqueue sync jobs for users whose sync_hour matches the current hour."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(self) -> dict:
        current_hour = datetime.now(UTC).hour
        logger.info(f"HourlySyncScheduler: running for hour {current_hour}")

        # Find users with this sync_hour who have Garmin credentials
        garmin_result = await self._db.execute(
            select(GarminCredentials.user_id)
            .join(User, User.id == GarminCredentials.user_id)
            .where(User.sync_hour == current_hour)
        )
        garmin_user_ids = garmin_result.scalars().all()

        # Find users with this sync_hour who have Xert credentials
        xert_result = await self._db.execute(
            select(XertCredentials.user_id)
            .join(User, User.id == XertCredentials.user_id)
            .where(User.sync_hour == current_hour)
        )
        xert_user_ids = xert_result.scalars().all()

        if not garmin_user_ids and not xert_user_ids:
            logger.info(f"HourlySyncScheduler: no users scheduled for hour {current_hour}")
            return {"success": True, "garmin_queued": 0, "xert_queued": 0}

        # Enqueue Garmin syncs immediately
        for user_id in garmin_user_ids:
            await enqueue_sync_garmin_job(user_id)
            logger.info(f"HourlySyncScheduler: enqueued Garmin sync for user {user_id}")

        # Enqueue Xert syncs with 15 minute delay to stagger
        defer_until = time.time() + (15 * 60)
        for user_id in xert_user_ids:
            await enqueue_sync_xert_job(user_id, scheduled=defer_until)
            logger.info(f"HourlySyncScheduler: enqueued Xert sync for user {user_id} (deferred 15min)")

        logger.info(f"HourlySyncScheduler: queued {len(garmin_user_ids)} Garmin, {len(xert_user_ids)} Xert syncs")
        return {"success": True, "garmin_queued": len(garmin_user_ids), "xert_queued": len(xert_user_ids)}
