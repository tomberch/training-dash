"""
PostgreSQL implementation of ActivityRepo.

Uses SQLAlchemy async session for all database operations.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Activity, Route


def _apply_activity_type_filter(query, activity_type: str | None):
    """Apply activity_type filter to a query.

    Args:
        query: SQLAlchemy select query
        activity_type: None = no filter, "" = unclassified (NULL), else specific type
    """
    if activity_type is None:
        return query
    if activity_type == "":
        # Empty string means unclassified (NULL in DB)
        return query.where(Activity.activity_type.is_(None))
    return query.where(Activity.activity_type == activity_type)


class PostgresActivityRepo:
    """
    PostgreSQL implementation of the ActivityRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, activity_id: UUID, user_id: int) -> Activity | None:
        """
        Fetch an activity by ID, scoped to the given user.

        Returns None if not found or not owned by user.
        """
        result = await self._session.execute(
            select(Activity).where(
                Activity.id == activity_id,
                Activity.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        activity_type: str | None = None,
    ) -> list[Activity]:
        """
        List activities for a user, ordered by started_at descending.

        Args:
            activity_type: Filter by type. None = all, "" = unclassified only.
        """
        query = select(Activity).where(Activity.user_id == user_id)
        query = _apply_activity_type_filter(query, activity_type)

        result = await self._session.execute(
            query.order_by(Activity.started_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: int, activity_type: str | None = None) -> int:
        """Count total activities for a user, optionally filtered by type."""
        query = select(func.count(Activity.id)).where(Activity.user_id == user_id)
        query = _apply_activity_type_filter(query, activity_type)

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def save(self, activity: Activity) -> Activity:
        """
        Persist an activity (insert or update).

        Returns the saved activity with any DB-generated fields populated.
        """
        self._session.add(activity)
        await self._session.commit()
        await self._session.refresh(activity)
        return activity

    async def delete(self, activity_id: UUID, user_id: int) -> bool:
        """
        Delete an activity owned by the given user.

        Handles cascade cleanup (records, laps, peaks via DB cascades) and
        route maintenance (ride_count decrement, orphan route deletion).

        Returns True if deleted, False if not found.
        """
        # Fetch the activity first to check ownership and get route_id
        activity = await self.get_by_id(activity_id, user_id)
        if activity is None:
            return False

        # Handle route maintenance before deletion
        if activity.route_id is not None:
            route_result = await self._session.execute(select(Route).where(Route.id == activity.route_id))
            route = route_result.scalar_one_or_none()

            if route is not None:
                if route.ride_count <= 1:
                    # Sole activity on route — delete the route after nulling FK
                    await self._session.execute(
                        sql_text("UPDATE activities SET route_id = NULL WHERE id = :aid"),
                        {"aid": activity_id},
                    )
                    await self._session.execute(
                        sql_text("DELETE FROM routes WHERE id = :rid"),
                        {"rid": route.id},
                    )
                else:
                    # Decrement ride_count; ON DELETE SET NULL handles first_seen
                    await self._session.execute(
                        sql_text("UPDATE routes SET ride_count = ride_count - 1 WHERE id = :rid"),
                        {"rid": route.id},
                    )
                    await self._session.execute(
                        sql_text("UPDATE activities SET route_id = NULL WHERE id = :aid"),
                        {"aid": activity_id},
                    )

        # Delete the activity (cascades Records, Laps, ActivityPeakPower)
        await self._session.execute(
            sql_text("DELETE FROM activities WHERE id = :aid"),
            {"aid": activity_id},
        )
        await self._session.commit()
        return True

    async def list_by_route(
        self,
        route_id: int,
        user_id: int,
        exclude_activity_id: UUID | None = None,
    ) -> list[Activity]:
        """
        List activities on a specific route for a user.
        """
        query = select(Activity).where(
            Activity.route_id == route_id,
            Activity.user_id == user_id,
        )

        if exclude_activity_id is not None:
            query = query.where(Activity.id != exclude_activity_id)

        result = await self._session.execute(query.order_by(Activity.started_at.desc()))
        return list(result.scalars().all())

    async def list_by_bike(
        self,
        bike_id: int,
        user_id: int,
        limit: int = 50,
    ) -> list[Activity]:
        """
        List activities tagged to a specific bike for a user.
        """
        result = await self._session.execute(
            select(Activity)
            .where(Activity.bike_id == bike_id, Activity.user_id == user_id)
            .order_by(Activity.started_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
