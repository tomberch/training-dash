"""
PostgreSQL implementations of Segment repositories.

Uses SQLAlchemy async session and PostGIS for spatial queries.
"""

from datetime import datetime
from uuid import UUID

from geoalchemy2.functions import ST_Buffer, ST_Intersects, ST_MakeEnvelope
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import (
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)


class PostgresSegmentRepo:
    """
    PostgreSQL implementation of the SegmentRepo protocol.

    Handles segment CRUD with PostGIS spatial queries for matching.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, segment_id: UUID) -> Segment | None:
        """Fetch a segment by ID. Returns None if not found or soft-deleted."""
        result = await self._session.execute(
            select(Segment).where(
                Segment.id == segment_id,
                Segment.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_approved(
        self,
        type: str | None = None,
        category: list[str] | None = None,
        bounds: tuple[float, float, float, float] | None = None,
        search: str | None = None,
        sort: str = "popularity",
        order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[Segment]:
        """
        List approved segments with optional filters.

        Args:
            type: Filter by segment type ('climb', 'sprint', 'custom')
            category: Filter by climb category (['hc', '1', '2', '3', '4', 'nc'])
            bounds: Bounding box (sw_lat, sw_lng, ne_lat, ne_lng) for spatial filter
            search: Text search on segment name (ILIKE)
            sort: Sort field ('popularity', 'name', 'distance', 'elevation')
            order: Sort order ('asc', 'desc')
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of approved Segment objects
        """
        query = select(Segment).where(
            Segment.status == "approved",
            Segment.deleted_at.is_(None),
        )

        # Apply filters
        if type:
            query = query.where(Segment.type == type)

        if category:
            query = query.where(Segment.climb_category.in_(category))

        if bounds:
            sw_lat, sw_lng, ne_lat, ne_lng = bounds
            # Create envelope and check intersection with segment bounds
            envelope = ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
            query = query.where(ST_Intersects(Segment.bounds, envelope))

        if search:
            query = query.where(Segment.name.ilike(f"%{search}%"))

        # Apply sorting
        sort_column = {
            "popularity": Segment.effort_count,
            "name": Segment.name,
            "distance": Segment.distance_m,
            "elevation": Segment.elevation_gain_m,
        }.get(sort, Segment.effort_count)

        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_approved(
        self,
        type: str | None = None,
        category: list[str] | None = None,
        bounds: tuple[float, float, float, float] | None = None,
        search: str | None = None,
    ) -> int:
        """Count approved segments matching the given filters."""
        query = select(func.count(Segment.id)).where(
            Segment.status == "approved",
            Segment.deleted_at.is_(None),
        )

        if type:
            query = query.where(Segment.type == type)

        if category:
            query = query.where(Segment.climb_category.in_(category))

        if bounds:
            sw_lat, sw_lng, ne_lat, ne_lng = bounds
            envelope = ST_MakeEnvelope(sw_lng, sw_lat, ne_lng, ne_lat, 4326)
            query = query.where(ST_Intersects(Segment.bounds, envelope))

        if search:
            query = query.where(Segment.name.ilike(f"%{search}%"))

        result = await self._session.execute(query)
        return result.scalar_one()

    async def save(self, segment: Segment) -> Segment:
        """
        Persist a segment (insert or update).

        Returns the saved segment with any DB-generated fields populated.
        """
        self._session.add(segment)
        await self._session.commit()
        await self._session.refresh(segment)
        return segment

    async def soft_delete(self, segment_id: UUID) -> bool:
        """
        Soft-delete a segment by setting deleted_at.

        Returns True if deleted, False if not found.
        """
        result = await self._session.execute(
            update(Segment)
            .where(
                Segment.id == segment_id,
                Segment.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now())
        )
        await self._session.commit()
        return result.rowcount > 0

    async def find_candidates_for_matching(
        self,
        bounds: object,  # WKBElement
        direction_bearing: float,
    ) -> list[Segment]:
        """
        Find approved segments that might match an activity section.

        Uses spatial intersection with 50m buffer and direction within ±60°.

        Args:
            bounds: PostGIS polygon covering the activity section
            direction_bearing: Travel direction in degrees (0-360)

        Returns:
            List of candidate Segment objects for detailed matching
        """
        # Buffer the bounds by 50 meters for fuzzy matching
        buffered = ST_Buffer(bounds, 0.00045)  # ~50m in degrees at mid-latitudes

        # Direction matching: segment direction should be within ±60° of activity direction
        # Handle wraparound at 0/360
        direction_low = (direction_bearing - 60) % 360
        direction_high = (direction_bearing + 60) % 360

        if direction_low < direction_high:
            direction_filter = and_(
                Segment.direction_bearing >= direction_low,
                Segment.direction_bearing <= direction_high,
            )
        else:
            # Wraparound case (e.g., bearing 350 ± 60 = 290-50)
            direction_filter = or_(
                Segment.direction_bearing >= direction_low,
                Segment.direction_bearing <= direction_high,
            )

        query = select(Segment).where(
            Segment.status == "approved",
            Segment.deleted_at.is_(None),
            ST_Intersects(Segment.bounds, buffered),
            or_(
                Segment.direction_bearing.is_(None),  # Allow segments without direction
                direction_filter,
            ),
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def increment_counts(self, segment_id: UUID, new_athlete: bool) -> None:
        """
        Increment effort_count and optionally athlete_count.

        Args:
            segment_id: Segment to update
            new_athlete: If True, also increment athlete_count
        """
        values = {"effort_count": Segment.effort_count + 1}
        if new_athlete:
            values["athlete_count"] = Segment.athlete_count + 1

        await self._session.execute(update(Segment).where(Segment.id == segment_id).values(**values))
        await self._session.commit()


class PostgresSegmentEffortRepo:
    """
    PostgreSQL implementation of the SegmentEffortRepo protocol.

    Handles effort CRUD and PR tracking.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, effort_id: UUID) -> SegmentEffort | None:
        """Fetch an effort by ID. Returns None if not found."""
        result = await self._session.execute(select(SegmentEffort).where(SegmentEffort.id == effort_id))
        return result.scalar_one_or_none()

    async def list_for_segment(
        self,
        segment_id: UUID,
        user_id: int,
        sort: str = "time",
        order: str = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[SegmentEffort]:
        """
        List a user's efforts on a segment.

        Args:
            segment_id: Segment ID
            user_id: User ID
            sort: Sort field ('time', 'date', 'power')
            order: Sort order ('asc', 'desc')
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of SegmentEffort objects
        """
        query = select(SegmentEffort).where(
            SegmentEffort.segment_id == segment_id,
            SegmentEffort.user_id == user_id,
        )

        # Apply sorting
        sort_column = {
            "time": SegmentEffort.elapsed_time_seconds,
            "date": SegmentEffort.started_at,
            "power": SegmentEffort.avg_power_watts,
        }.get(sort, SegmentEffort.elapsed_time_seconds)

        if order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_for_activity(self, activity_id: UUID) -> list[SegmentEffort]:
        """
        List all efforts from an activity, ordered by start_index.

        Returns:
            List of SegmentEffort objects in ride order
        """
        result = await self._session.execute(
            select(SegmentEffort)
            .where(SegmentEffort.activity_id == activity_id)
            .order_by(SegmentEffort.start_index.asc())
        )
        return list(result.scalars().all())

    async def save(self, effort: SegmentEffort) -> SegmentEffort:
        """
        Persist an effort (insert or update).

        Returns the saved effort with any DB-generated fields populated.
        """
        self._session.add(effort)
        await self._session.commit()
        await self._session.refresh(effort)
        return effort

    async def get_user_pr(self, segment_id: UUID, user_id: int) -> SegmentEffort | None:
        """
        Get the user's PR effort on a segment.

        Returns the effort with is_pr=True, or None if no efforts exist.
        """
        result = await self._session.execute(
            select(SegmentEffort).where(
                SegmentEffort.segment_id == segment_id,
                SegmentEffort.user_id == user_id,
                SegmentEffort.is_pr.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def clear_user_pr(self, segment_id: UUID, user_id: int) -> None:
        """
        Clear the is_pr flag on all of a user's efforts for a segment.

        Called before setting a new PR.
        """
        await self._session.execute(
            update(SegmentEffort)
            .where(
                SegmentEffort.segment_id == segment_id,
                SegmentEffort.user_id == user_id,
                SegmentEffort.is_pr.is_(True),
            )
            .values(is_pr=False)
        )
        await self._session.commit()

    async def count_for_segment(self, segment_id: UUID, user_id: int) -> int:
        """Count a user's efforts on a segment."""
        result = await self._session.execute(
            select(func.count(SegmentEffort.id)).where(
                SegmentEffort.segment_id == segment_id,
                SegmentEffort.user_id == user_id,
            )
        )
        return result.scalar_one()


class PostgresSegmentSuggestionRepo:
    """
    PostgreSQL implementation of the SegmentSuggestionRepo protocol.

    Handles suggestion CRUD and dismissal.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, suggestion_id: UUID) -> SegmentSuggestion | None:
        """Fetch a suggestion by ID. Returns None if not found."""
        result = await self._session.execute(select(SegmentSuggestion).where(SegmentSuggestion.id == suggestion_id))
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        include_dismissed: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SegmentSuggestion]:
        """
        List suggestions for a user.

        Args:
            user_id: User ID
            include_dismissed: If True, include dismissed suggestions
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of SegmentSuggestion objects ordered by repetition_count desc
        """
        query = select(SegmentSuggestion).where(SegmentSuggestion.user_id == user_id)

        if not include_dismissed:
            query = query.where(SegmentSuggestion.dismissed_at.is_(None))

        query = query.order_by(SegmentSuggestion.repetition_count.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: int, include_dismissed: bool = False) -> int:
        """Count suggestions for a user."""
        query = select(func.count(SegmentSuggestion.id)).where(SegmentSuggestion.user_id == user_id)

        if not include_dismissed:
            query = query.where(SegmentSuggestion.dismissed_at.is_(None))

        result = await self._session.execute(query)
        return result.scalar_one()

    async def save(self, suggestion: SegmentSuggestion) -> SegmentSuggestion:
        """
        Persist a suggestion (insert or update).

        Returns the saved suggestion with any DB-generated fields populated.
        """
        self._session.add(suggestion)
        await self._session.commit()
        await self._session.refresh(suggestion)
        return suggestion

    async def dismiss(self, suggestion_id: UUID) -> bool:
        """
        Dismiss a suggestion by setting dismissed_at.

        Returns True if dismissed, False if not found.
        """
        result = await self._session.execute(
            update(SegmentSuggestion)
            .where(
                SegmentSuggestion.id == suggestion_id,
                SegmentSuggestion.dismissed_at.is_(None),
            )
            .values(dismissed_at=datetime.now())
        )
        await self._session.commit()
        return result.rowcount > 0

    async def dismiss_all(self, user_id: int) -> int:
        """
        Dismiss all suggestions for a user.

        Returns the count of suggestions dismissed.
        """
        result = await self._session.execute(
            update(SegmentSuggestion)
            .where(
                SegmentSuggestion.user_id == user_id,
                SegmentSuggestion.dismissed_at.is_(None),
            )
            .values(dismissed_at=datetime.now())
        )
        await self._session.commit()
        return result.rowcount

    async def get_for_user_segment(self, user_id: int, segment_id: UUID) -> SegmentSuggestion | None:
        """
        Get the suggestion for a specific user/segment pair.

        Returns None if no suggestion exists.
        """
        result = await self._session.execute(
            select(SegmentSuggestion).where(
                SegmentSuggestion.user_id == user_id,
                SegmentSuggestion.segment_id == segment_id,
            )
        )
        return result.scalar_one_or_none()
