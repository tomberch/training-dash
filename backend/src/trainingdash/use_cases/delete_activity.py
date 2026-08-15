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

    def __init__(self, activity_repo: ActivityRepo, db: AsyncSession) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            activity_repo: Repository for activity persistence
            db: Database session for event logging
        """
        self._activity_repo = activity_repo
        self._event_repo = PostgresEventRepo(db)

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

        # Step 2: Enqueue fitness recalculation
        from trainingdash.jobs import enqueue_recalculate_after_delete_job

        try:
            await enqueue_recalculate_after_delete_job(user_id)
        except Exception:
            # Log but don't fail - deletion succeeded, recalc can be retried
            logger.exception(
                "Failed to enqueue recalculation after deleting activity %s for user %s",
                activity_id,
                user_id,
            )

        return True
