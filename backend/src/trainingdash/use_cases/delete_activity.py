"""
DeleteActivity use case — orchestrates activity deletion.

This use case handles the complete flow of deleting an activity:
1. Verify ownership and delete activity via repository
2. Enqueue background job for fitness model recalculation
"""

import logging
from uuid import UUID

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
        use_case = DeleteActivity(activity_repo)
        deleted = await use_case.execute(user_id=1, activity_id=uuid)
        if not deleted:
            raise NotFoundError()
    """

    def __init__(self, activity_repo: ActivityRepo) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            activity_repo: Repository for activity persistence
        """
        self._activity_repo = activity_repo

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
