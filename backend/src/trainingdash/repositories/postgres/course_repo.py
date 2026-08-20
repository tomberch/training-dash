"""
PostgreSQL implementation of CourseRepo.

Uses SQLAlchemy async session for all database operations.
"""

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import RaceCourse


class PostgresCourseRepo:
    """
    PostgreSQL implementation of the CourseRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, course_id: int, user_id: int) -> RaceCourse | None:
        """
        Fetch a course by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        result = await self._session.execute(
            select(RaceCourse)
            .where(
                RaceCourse.id == course_id,
                RaceCourse.user_id == user_id,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> list[RaceCourse]:
        """
        List courses for a user, ordered by created_at descending.

        Returns:
            List of RaceCourse objects
        """
        result = await self._session.execute(
            select(RaceCourse)
            .where(RaceCourse.user_id == user_id)
            .order_by(RaceCourse.created_at.desc())
        )
        return list(result.scalars().all())

    async def save(self, course: RaceCourse) -> RaceCourse:
        """
        Persist a course (insert or update).

        Returns the saved course with any DB-generated fields populated.
        """
        self._session.add(course)
        await self._session.commit()
        await self._session.refresh(course)
        return course

    async def delete(self, course_id: int, user_id: int) -> bool:
        """
        Delete a course.

        Returns True if deleted, False if not found.
        """
        result = await self._session.execute(
            delete(RaceCourse).where(
                RaceCourse.id == course_id,
                RaceCourse.user_id == user_id,
            )
        )
        await self._session.commit()
        return result.rowcount > 0

    async def update_processed_data(
        self,
        course_id: int,
        user_id: int,
        elevation_profile: list[dict],
        segments: list[dict],
        climbs: list[dict],
    ) -> None:
        """
        Update the processed data for a course.

        Args:
            course_id: Course ID
            user_id: Owner's user ID (for security scoping)
            elevation_profile: List of {distance_m, elevation_m, grade_pct}
            segments: List of {start_m, end_m, avg_grade_pct, distance_m, ...}
            climbs: List of {name, start_m, end_m, avg_grade_pct, category, ...}
        """
        await self._session.execute(
            update(RaceCourse)
            .where(
                RaceCourse.id == course_id,
                RaceCourse.user_id == user_id,
            )
            .values(
                elevation_profile=elevation_profile,
                segments=segments,
                climbs=climbs,
                updated_at=datetime.now(),
            )
        )
        await self._session.commit()
