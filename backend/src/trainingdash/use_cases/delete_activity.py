"""
DeleteActivity use case — orchestrates activity deletion.

This use case handles the complete flow of deleting an activity:
1. Verify ownership and delete activity via repository
2. Enqueue background job for fitness model recalculation
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.protocols import ActivityRepo

logger = logging.getLogger(__name__)


class DeleteActivity:
    """
    Use case for deleting an activity.

    This use case coordinates:
    - Ownership verification and deletion (delegated to ActivityRepo)
    - Route maintenance (ride_count, orphan cleanup - handled by repo)
    - Triggering background recalculation of fitness metrics

    Example usage:
        use_case = DeleteActivity(activity_repo, db)
        deleted = await use_case.execute(user_id=1, activity_id=uuid)
        if not deleted:
            raise NotFoundError()
    """

    def __init__(self, activity_repo: ActivityRepo, db: AsyncSession | None = None, segment_repo=None, event_repo=None) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            activity_repo: Repository for activity persistence
            db: Database session for event logging
            segment_repo: Optional (unused here; kept for DI symmetry)
            event_repo: Optional event repo override (defaults to Postgres on db)
        """
        self._activity_repo = activity_repo
        self._db = db
        self._event_repo = event_repo or PostgresEventRepo(db)

    async def execute(self, user_id: int, activity_id: UUID) -> bool:
        """
        Delete an activity owned by the given user.

        Steps:
        1. Verify ownership and delete activity (repo handles route maintenance)
        2. Enqueue fitness model recalculation job

        Args:
            user_id: The user ID who owns the activity
            activity_id: The activity to delete

        Returns:
            True if deleted, False if not found or not owned by user
        """
        # Step 1: Delete via repository (handles ownership, route maintenance)
        deleted = await self._activity_repo.delete(activity_id, user_id)

        if not deleted:
            return False

        # Emit delete event
        await self._event_repo.log(
            event_type=EventType.ACTIVITY_DELETED.value,
            outcome=EventOutcome.INFO.value,
            user_id=user_id,
            payload={"activity_id": str(activity_id)},
        )

        # Step 2: Enqueue fitness recalculation (Class B policy, ADR 0006 decision 3):
        # the deletion succeeded, so a lost follow-up must never fail the endpoint —
        # record job.enqueue_failed (with the affected user) and move on.
        from trainingdash.jobs import enqueue_recalculate_after_delete_job

        try:
            job_key = await enqueue_recalculate_after_delete_job(user_id)
            if job_key is None:
                await self._log_enqueue_failed(user_id, activity_id, reason="queue unavailable (dev mode)")
        except Exception as exc:
            # Class B (ADR 0006, decision 3): deletion succeeded; a lost
            # follow-up is recorded (event + user notification), never raised.
            logger.exception(
                "Failed to enqueue recalculation after deleting activity %s for user %s",
                activity_id,
                user_id,
            )
            await self._log_enqueue_failed(user_id, activity_id, reason=str(exc))

        return True

    async def _log_enqueue_failed(self, user_id: int, activity_id: UUID, reason: str) -> None:
        """Record the lost recalc-after-delete follow-up for the admin surface."""
        try:
            await self._event_repo.log(
                event_type="job.enqueue_failed",
                outcome="failure",
                user_id=user_id,
                payload={
                    "job": "recalculate_after_delete_job",
                    "reason": reason,
                    "activity_id": str(activity_id),
                },
            )
            await self._notify_user(user_id, "recalculate_after_delete_job", reason)
        except Exception:
            logger.exception("Failed to record job.enqueue_failed event for user %s", user_id)

    async def _notify_user(self, user_id: int, job: str, reason: str) -> None:
        """Notify the affected user that a follow-up job was lost (ADR 0006, decision 3)."""
        try:
            import json

            from trainingdash.repositories.postgres.models import Notification

            notification = Notification(
                user_id=user_id,
                type="job_lost",
                message="A background update (fitness recalculation) could not be scheduled. "
                "It will retry automatically; your data is safe.",
                payload=json.dumps({"job": job, "reason": reason}),
                status="pending",
            )
            self._db.add(notification)
            await self._db.flush()
        except Exception:
            logger.exception("Failed to notify user %s about lost job", user_id)
