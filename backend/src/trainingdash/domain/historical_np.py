"""Historical NP stats for course-to-route matching.

Matches a race course's geometry against routes to find historical rides
on the same or similar course, then computes NP statistics.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# Use same threshold as activity route matching for consistency
HAUSDORFF_THRESHOLD_M = 500.0


@dataclass
class HistoricalNpStats:
    """NP statistics from historical rides on a matched route."""

    ride_count: int
    avg_np_w: float
    min_np_w: float
    max_np_w: float
    avg_power_w: float  # Average of avg_power across rides


async def find_route_for_course(
    db: AsyncSession,
    user_id: int,
    course_id: int,
    threshold_m: float = HAUSDORFF_THRESHOLD_M,
) -> int | None:
    """Find the route that matches a course's geometry.

    Compares the course's LineStringZ geometry (with elevation stripped)
    against the user's routes using Hausdorff distance.

    Args:
        db: Database session.
        user_id: User ID to scope routes.
        course_id: Course ID to match.
        threshold_m: Maximum Hausdorff distance in meters for a match.

    Returns:
        Route ID if a match is found within threshold, None otherwise.
    """
    # Convert threshold to approximate degrees (at mid-latitude ~45°)
    # More accurate would be to use the course's actual latitude
    threshold_deg = threshold_m / 111000.0 / 0.707  # ~cos(45°)

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

    result = await db.execute(query)
    row = result.first()

    if row is None:
        return None

    if row.distance is not None and row.distance <= threshold_deg:
        return row.id

    return None


async def get_historical_np_stats(
    db: AsyncSession,
    user_id: int,
    route_id: int,
) -> HistoricalNpStats | None:
    """Get NP statistics for activities on a route.

    Args:
        db: Database session.
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
            MAX(np_power_w) AS max_np_w,
            AVG(avg_power_w) AS avg_power_w
        FROM activities
        WHERE user_id = :user_id
          AND route_id = :route_id
          AND np_power_w IS NOT NULL
    """).bindparams(user_id=user_id, route_id=route_id)

    result = await db.execute(query)
    row = result.first()

    if row is None or row.ride_count == 0:
        return None

    return HistoricalNpStats(
        ride_count=row.ride_count,
        avg_np_w=float(row.avg_np_w),
        min_np_w=float(row.min_np_w),
        max_np_w=float(row.max_np_w),
        avg_power_w=float(row.avg_power_w),
    )


async def get_course_historical_np(
    db: AsyncSession,
    user_id: int,
    course_id: int,
) -> HistoricalNpStats | None:
    """Get historical NP stats for a course by matching to routes.

    Convenience function that combines route matching and stats lookup.

    Args:
        db: Database session.
        user_id: User ID.
        course_id: Course ID.

    Returns:
        HistoricalNpStats if a matching route with rides exists, None otherwise.
    """
    route_id = await find_route_for_course(db, user_id, course_id)
    if route_id is None:
        return None

    return await get_historical_np_stats(db, user_id, route_id)
