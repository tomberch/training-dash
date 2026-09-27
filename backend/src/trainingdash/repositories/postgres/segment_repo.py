"""
PostgreSQL implementations of Segment repositories.

Uses SQLAlchemy async session and PostGIS for spatial queries.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import WKTElement
from geoalchemy2.functions import (
    ST_Buffer,
    ST_DWithin,
    ST_Intersects,
    ST_MakeEnvelope,
)
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.segment_geometry import SegmentGeometry
from trainingdash.domain.segment_matching import (
    SUGGESTION_VISIBILITY_THRESHOLD,
    SegmentForDedup,
    find_duplicate_segment,
)
from trainingdash.repositories.postgres.models import (
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)

logger = logging.getLogger(__name__)


def extract_point_coords(point: Any) -> tuple[float, float]:
    """
    Extract (lat, lon) from a PostGIS geometry or test fake.

    Handles:
    - GeoAlchemy2 WKBElement (real Postgres) — uses to_shape
    - WKTElement (used in test fixtures) — parses "POINT(lon lat)"
    - Objects with .x/.y attributes (test fakes)
    - Tuples (lat, lon) — returned as-is

    Args:
        point: A geometry object from PostGIS or a test fake.

    Returns:
        Tuple of (latitude, longitude).

    Raises:
        ValueError: If coordinates cannot be extracted.
    """
    if point is None:
        raise ValueError("Cannot extract coordinates from None")

    # Tuples (lat, lon) from test fixtures
    if isinstance(point, tuple) and len(point) == 2:
        return point

    # Test fakes with .x/.y but no .data (not WKTElement)
    if hasattr(point, "x") and hasattr(point, "y") and not hasattr(point, "data"):
        return (point.y, point.x)

    # WKTElement: parse "POINT(lon lat)" format
    if hasattr(point, "data"):
        data = str(point.data)
        if data.startswith("POINT("):
            coords = data[6:-1].split()
            if len(coords) == 2:
                return (float(coords[1]), float(coords[0]))  # lat, lon

    # Real WKBElement from PostGIS
    try:
        from geoalchemy2.shape import to_shape

        shape = to_shape(point)
        return (shape.y, shape.x)  # lat, lon
    except Exception as e:
        logger.debug(f"Failed to extract coordinates via to_shape: {e}")

    raise ValueError(f"Cannot extract coordinates from {type(point)}")


def segment_to_dedup(segment: Segment) -> SegmentForDedup:
    """
    Convert a Segment ORM model to a SegmentForDedup for domain functions.

    Args:
        segment: A Segment ORM model with PostGIS geometry fields.

    Returns:
        A SegmentForDedup with extracted coordinates.
    """
    start_lat, start_lon = extract_point_coords(segment.start_point)
    end_lat, end_lon = extract_point_coords(segment.end_point)
    return SegmentForDedup(
        id=segment.id,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        polyline=segment.polyline,
    )


def segment_to_geometry(segment: Segment) -> SegmentGeometry:
    """
    Convert a Segment ORM model to a SegmentGeometry for domain functions.

    Used when a Segment's geometry needs to be passed to domain functions
    that expect SegmentGeometry (e.g., find_duplicate_segment for a
    suggestion being approved with adjusted endpoints).

    Args:
        segment: A Segment ORM model.

    Returns:
        A SegmentGeometry populated from the model's fields.
    """
    from trainingdash.domain.segment_geometry import ElevationPoint

    start_lat, start_lon = extract_point_coords(segment.start_point)
    end_lat, end_lon = extract_point_coords(segment.end_point)

    # Convert elevation_profile JSON back to ElevationPoint objects
    elevation_profile = []
    if segment.elevation_profile:
        for ep in segment.elevation_profile:
            elevation_profile.append(
                ElevationPoint(
                    distance_m=ep.get("distance_m", 0.0),
                    elevation_m=ep.get("elevation_m", 0.0),
                    grade_pct=ep.get("grade_pct", 0.0),
                )
            )

    # Extract bounds from PostGIS polygon or use defaults
    try:
        from geoalchemy2.shape import to_shape

        bounds_shape = to_shape(segment.bounds)
        min_lon, min_lat, max_lon, max_lat = bounds_shape.bounds
        bounds = (min_lat, min_lon, max_lat, max_lon)
    except Exception:
        # Fallback: derive bounds from start/end points
        bounds = (
            min(start_lat, end_lat),
            min(start_lon, end_lon),
            max(start_lat, end_lat),
            max(start_lon, end_lon),
        )

    return SegmentGeometry(
        polyline=segment.polyline,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
        bounds=bounds,
        direction_bearing=segment.direction_bearing or 0.0,
        distance_m=segment.distance_m or 0.0,
        elevation_gain_m=segment.elevation_gain_m or 0.0,
        avg_grade_pct=segment.avg_grade_pct or 0.0,
        max_grade_pct=segment.max_grade_pct or 0.0,
        elevation_profile=elevation_profile,
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

    async def find_similar_suggested(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        polyline: str,
    ) -> Segment | None:
        """
        Find an existing suggested segment describing the same road.

        Prefilters with a spatial query — suggested segments whose bounds
        come within 100m of the candidate start point — then applies the
        same-road containment criterion via find_duplicate_segment in Python.
        Containment is used instead of the strict is_same_segment gate
        because detected climb boundaries wobble between rides: repeat
        detections of one climb must merge so suggestion repetition
        counts reach the visibility threshold.

        Returns the matching Segment, or None.
        """
        # Cheap spatial prefilter: suggested segments near the start point.
        # Ordered deterministically (nearest first) so the limit always
        # keeps the most likely duplicates.
        start_point = WKTElement(f"POINT({start_lon} {start_lat})", srid=4326)
        candidates = (
            (
                await self._session.execute(
                    select(Segment)
                    .where(
                        Segment.status == "suggested",
                        Segment.deleted_at.is_(None),
                        ST_DWithin(Segment.start_point, start_point, 0.001),  # ~100m
                    )
                    .order_by(func.ST_Distance(Segment.start_point, start_point).asc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        if not candidates:
            return None

        # Build a minimal SegmentGeometry for the domain function.
        # Only start/end coords and polyline are needed for same_road mode.
        candidate_geometry = SegmentGeometry(
            polyline=polyline,
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            bounds=(0, 0, 0, 0),  # Not used in same_road mode
            direction_bearing=0.0,
            distance_m=0.0,
            elevation_gain_m=0.0,
            avg_grade_pct=0.0,
            max_grade_pct=0.0,
            elevation_profile=[],
        )

        # Convert ORM candidates to domain types
        existing = [segment_to_dedup(c) for c in candidates]

        # Use domain function for duplicate detection
        match = find_duplicate_segment(candidate_geometry, existing, mode="same_road")
        if match is None:
            return None

        # Return the full Segment ORM model
        return next((c for c in candidates if c.id == match.id), None)


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

        Only suggestions with repetition_count >=
        SUGGESTION_VISIBILITY_THRESHOLD are returned — climbs are
        proposed after 3+ repeat rides.

        Args:
            user_id: User ID
            include_dismissed: If True, include dismissed suggestions
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of SegmentSuggestion objects ordered by repetition_count desc
        """
        query = select(SegmentSuggestion).where(
            SegmentSuggestion.user_id == user_id,
            SegmentSuggestion.repetition_count >= SUGGESTION_VISIBILITY_THRESHOLD,
            or_(
                SegmentSuggestion.expires_at.is_(None),
                SegmentSuggestion.expires_at >= datetime.now(),
            ),
        )

        if not include_dismissed:
            query = query.where(SegmentSuggestion.dismissed_at.is_(None))

        query = query.order_by(SegmentSuggestion.repetition_count.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: int, include_dismissed: bool = False) -> int:
        """Count visible suggestions for a user (3+ repetitions only)."""
        query = select(func.count(SegmentSuggestion.id)).where(
            SegmentSuggestion.user_id == user_id,
            SegmentSuggestion.repetition_count >= SUGGESTION_VISIBILITY_THRESHOLD,
            or_(
                SegmentSuggestion.expires_at.is_(None),
                SegmentSuggestion.expires_at >= datetime.now(),
            ),
        )

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
        Dismiss all VISIBLE suggestions for a user (>= threshold).

        Below-threshold suggestions the user has never seen are left
        untouched — the confirm dialog quotes the visible total, so
        dismissing must not remove more than that.

        Returns the count of suggestions dismissed.
        """
        result = await self._session.execute(
            update(SegmentSuggestion)
            .where(
                SegmentSuggestion.user_id == user_id,
                SegmentSuggestion.dismissed_at.is_(None),
                SegmentSuggestion.repetition_count >= SUGGESTION_VISIBILITY_THRESHOLD,
                or_(
                    SegmentSuggestion.expires_at.is_(None),
                    SegmentSuggestion.expires_at >= datetime.now(),
                ),
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
