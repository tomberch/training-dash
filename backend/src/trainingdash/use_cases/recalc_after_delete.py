"""
RecalcAfterDelete use case — recompute fitness model + breakthrough flags after a delete.

Runs the two user-level recomputes (FitnessModelUpdater + BreakthroughEvaluator)
that need to happen after an activity is deleted, so the DELETE endpoint can
return 204 immediately. Idempotent — safe to re-run after partial failure.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.use_cases.breakthrough_evaluator import BreakthroughEvaluator
from trainingdash.use_cases.fitness_model_updater import FitnessModelUpdater

logger = logging.getLogger(__name__)


class RecalcAfterDelete:
    """Recompute fitness model and breakthrough flags for a user after a delete."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def execute(self, user_id: int) -> dict:
        """Run FitnessModelUpdater then BreakthroughEvaluator. Each step is
        isolated — a failure in one doesn't skip the other."""
        # Step 1: Recompute fitness model (FitnessHistory snapshot)
        try:
            await FitnessModelUpdater(self._db).execute(user_id)
            await self._db.commit()
        except Exception:
            logger.exception(
                "RecalcAfterDelete: fitness model update failed for user %s",
                user_id,
            )

        # Step 2: Re-evaluate is_breakthrough on all remaining activities
        try:
            await BreakthroughEvaluator(self._db).execute(user_id)
            await self._db.commit()
        except Exception:
            logger.exception(
                "RecalcAfterDelete: breakthrough re-evaluation failed for user %s",
                user_id,
            )

        return {"success": True, "user_id": user_id}