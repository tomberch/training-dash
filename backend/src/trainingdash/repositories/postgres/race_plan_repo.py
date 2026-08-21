"""
PostgreSQL implementation of RacePlanRepo.

Uses SQLAlchemy async session for all database operations.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import RacePlan


class PostgresRacePlanRepo:
    """
    PostgreSQL implementation of the RacePlanRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, plan_id: int, user_id: int) -> RacePlan | None:
        """
        Fetch a race plan by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        result = await self._session.execute(
            select(RacePlan)
            .where(
                RacePlan.id == plan_id,
                RacePlan.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_course(self, course_id: int, user_id: int) -> list[RacePlan]:
        """
        List race plans for a course, ordered by created_at descending.

        Args:
            course_id: Course ID
            user_id: Owner's user ID

        Returns:
            List of RacePlan objects
        """
        result = await self._session.execute(
            select(RacePlan)
            .where(
                RacePlan.course_id == course_id,
                RacePlan.user_id == user_id,
            )
            .order_by(RacePlan.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_user(self, user_id: int, limit: int = 20) -> list[RacePlan]:
        """
        List race plans for a user, ordered by created_at descending.

        Args:
            user_id: Owner's user ID
            limit: Maximum number of plans to return

        Returns:
            List of RacePlan objects
        """
        result = await self._session.execute(
            select(RacePlan).where(RacePlan.user_id == user_id).order_by(RacePlan.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def save(self, plan: RacePlan) -> RacePlan:
        """
        Persist a race plan (insert or update).

        Returns the saved plan with any DB-generated fields populated.
        """
        self._session.add(plan)
        await self._session.commit()
        await self._session.refresh(plan)
        return plan

    async def delete(self, plan_id: int, user_id: int) -> bool:
        """
        Delete a race plan.

        Returns True if deleted, False if not found.
        """
        result = await self._session.execute(
            delete(RacePlan).where(
                RacePlan.id == plan_id,
                RacePlan.user_id == user_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0
