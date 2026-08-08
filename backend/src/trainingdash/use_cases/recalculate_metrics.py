"""
RecalculateMetrics use case — recompute training metrics for user's activities.

This use case handles recomputing metrics (NP, IF, TSS, W'bal, zone times)
for all activities with power data when thresholds change.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.protocols import RecalculationJobRepo

logger = logging.getLogger(__name__)


@dataclass
class RecalculationResult:
    """Result of a metrics recalculation operation."""
    success: bool
    user_id: int
    activities_updated: int = 0
    error: str | None = None


class RecalculateMetrics:
    """
    Use case for recalculating training metrics for a user's activities.
    
    This use case coordinates:
    - Tracking job status (pending → running → completed/failed)
    - Computing metrics for activities missing them
    - Updating activities with new metric values
    
    Example usage:
        use_case = RecalculateMetrics(db, recalculation_job_repo)
        result = await use_case.execute(user_id=1)
    """

    def __init__(
        self,
        db: AsyncSession,
        recalculation_job_repo: RecalculationJobRepo | None = None,
    ) -> None:
        """
        Initialize the use case with dependencies.
        
        Args:
            db: Database session for persistence
            recalculation_job_repo: Optional repo for tracking job status.
                If None, job status tracking is skipped.
        """
        self._db = db
        self._job_repo = recalculation_job_repo

    async def execute(self, user_id: int) -> RecalculationResult:
        """
        Recalculate metrics for all activities with power data for a user.
        
        Steps:
        1. Mark job as running (if job_repo provided)
        2. Find activities missing metrics but with power data
        3. For each activity, compute NP, IF, TSS, W'bal, zone times
        4. Update activities in database
        5. Mark job as completed or failed
        
        Args:
            user_id: User whose activities should be recalculated
        
        Returns:
            RecalculationResult with success status and count of updated activities
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Mark job as running
        if self._job_repo:
            await self._job_repo.mark_running(user_id)
            await self._db.commit()
        
        try:
            # Import here to avoid circular imports
            from trainingdash.ingest import backfill_activity_metrics
            
            count = await backfill_activity_metrics(self._db, user_id)
            completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            # Mark job as completed
            if self._job_repo:
                await self._job_repo.mark_completed(user_id, count)
                await self._db.commit()
            
            logger.info(
                "RecalculateMetrics: completed for user %s — %d activities updated",
                user_id,
                count,
            )
            
            return RecalculationResult(
                success=True,
                user_id=user_id,
                activities_updated=count,
            )
        
        except Exception as exc:
            error_msg = str(exc)[:500]
            
            # Mark job as failed
            if self._job_repo:
                try:
                    await self._job_repo.mark_failed(user_id, error_msg)
                    await self._db.commit()
                except Exception:
                    logger.exception(
                        "RecalculateMetrics: failed to persist failure state for user %s",
                        user_id,
                    )
            
            logger.exception(
                "RecalculateMetrics: failed for user %s", user_id
            )
            
            return RecalculationResult(
                success=False,
                user_id=user_id,
                error=error_msg,
            )
