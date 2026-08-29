"""
PostgreSQL implementation of HistoricalNpRepo.

Uses PostGIS spatial operations to match courses to routes and compute
historical NP statistics from activities on those routes.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.historical_np import HistoricalNpStats


# Coordinate conversion constants for Hausdorff distance threshold
# Convert meters to approximate degrees at mid-latitude (~45°)
METERS_PER_DEGREE = 111_000.0
COS_45_DEGREES = 0.707  # Approximate cos(45°) for latitude adjustment

# Hausdorff threshold per spec: ~100m for course-to-route matching
HAUSDORFF_THRESHOLD_M = 100.0


def meters_to_degrees(meters: float) -> float:
    """Convert meters to approximate degrees at mid-latitude (~45°).

    This is an approximation that works reasonably well for courses
    at latitudes between ~30° and ~60°. For extreme latitudes,
    accuracy decreases.
    """
    return meters / METERS_PER_DEGREE / COS_45_DEGREES


class PostgresHistoricalNpRepo:
    """
    PostgreSQL implementation of the HistoricalNpRepo protocol.

    Uses PostGIS spatial operations:
    - ST_HausdorffDistance for course-to-route geometry matching
    - ST_Force2D to strip elevation from course LineStringZ geometries
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_route_for_course(
        self,
        user_id: int,
        course_id: int,
        threshold_m: float = HAUSDORFF_THRESHOLD_M,
    ) -> int | None:
        """Find the route that matches a course's geometry.

        Compares the course's LineStringZ geometry (with elevation stripped)
        against the user's routes using Hausdorff distance.

        Args:
            user_id: User ID to scope routes.
            course_id: Course ID to match.
            threshold_m: Maximum Hausdorff distance in meters for a match.

        Returns:
            Route ID if a match is found within threshold, None otherwise.
        """
        threshold_deg = meters_to_degrees(threshold_m)

        # Query to find closest matching route
        # ST_Force2D strips elevation from the course's LineStringZ
        query = text("""
            SELECT r.id, ST_HausdorffDistance(
                CAST(ST_Force2D(c.geometry) AS geometry),
                CAST(r.simplified_polyline AS geometry)
            ) AS distance
            FROM race_courses c
            CROSS JOIN routes r
            WHERE c.id = :course_id
              AND c.user_id = :user_id
              AND r.user_id = :user_id
            ORDER BY distance
            LIMIT 1
        """).bindparams(course_id=course_id, user_id=user_id)

        result = await self._session.execute(query)
        row = result.first()

        if row is None:
            return None

        if row.distance is not None and row.distance <= threshold_deg:
            return row.id

        return None

    async def get_stats_for_route(
        self,
        user_id: int,
        route_id: int,
    ) -> HistoricalNpStats | None:
        """Get NP statistics for activities on a route.

        Args:
            user_id: User ID to scope activities.
            route_id: Route ID to query.

        Returns:
            HistoricalNpStats if activities with NP exist, None otherwise.
        """
        query = text("""
            SELECT
                COUNT(*) AS ride_count,
                AVG(np_power_w) AS avg_np_w,
                MIN(np_power_w) AS min_np_w,
                MAX(np_power_w) AS best_np_w,
                AVG(avg_power_w) AS avg_power_w
            FROM activities
            WHERE user_id = :user_id
              AND route_id = :route_id
              AND np_power_w IS NOT NULL
        """).bindparams(user_id=user_id, route_id=route_id)

        result = await self._session.execute(query)
        row = result.first()

        if row is None or row.ride_count == 0:
            return None

        return HistoricalNpStats(
            ride_count=row.ride_count,
            avg_np_w=float(row.avg_np_w),
            min_np_w=float(row.min_np_w),
            best_np_w=float(row.best_np_w),
            avg_power_w=float(row.avg_power_w),
        )

    async def get_for_course(
        self,
        user_id: int,
        course_id: int,
    ) -> HistoricalNpStats | None:
        """Get historical NP stats for a course by matching to routes.

        Convenience method that combines route matching and stats lookup.

        Args:
            user_id: User ID.
            course_id: Course ID.

        Returns:
            HistoricalNpStats if a matching route with rides exists, None otherwise.
        """
        route_id = await self.find_route_for_course(user_id, course_id)
        if route_id is None:
            return None

        return await self.get_stats_for_route(user_id, route_id)
