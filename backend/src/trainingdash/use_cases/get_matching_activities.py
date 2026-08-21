"""
GetMatchingActivities use case.

Finds activities that could be compared against a race plan.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from trainingdash.repositories.protocols import (
    ActivityRepo,
    CourseRepo,
    RacePlanRepo,
)


@dataclass
class MatchingActivity:
    """Activity that matches a race plan's course."""

    id: UUID
    title: str | None
    started_at: datetime
    total_distance_m: float
    moving_time_s: int
    avg_power_w: float


class GetMatchingActivities:
    """
    Use case for finding activities comparable to a race plan.

    Filters activities by:
    - Having power data
    - Similar distance to the plan's course (within tolerance)
    """

    def __init__(
        self,
        plan_repo: RacePlanRepo,
        activity_repo: ActivityRepo,
        course_repo: CourseRepo,
    ) -> None:
        self._plan_repo = plan_repo
        self._activity_repo = activity_repo
        self._course_repo = course_repo

    async def execute(
        self,
        user_id: int,
        plan_id: int,
        distance_tolerance_pct: float = 0.2,
        limit: int = 20,
    ) -> list[MatchingActivity]:
        """
        Find activities that could be compared to a race plan.

        Args:
            user_id: User ID for access control
            plan_id: Race plan to find matches for
            distance_tolerance_pct: Allowed distance deviation (default 20%)
            limit: Maximum activities to return

        Returns:
            List of matching activities with power data

        Raises:
            ValueError: If plan or course not found
        """
        # Load plan
        plan = await self._plan_repo.get_by_id(plan_id, user_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")

        # Load course for distance reference
        course = await self._course_repo.get_by_id(plan.course_id, user_id)
        if course is None:
            raise ValueError(f"Course {plan.course_id} not found")

        # Get recent activities
        activities = await self._activity_repo.list_for_user(user_id, limit=50)

        # Filter by power data and distance similarity
        course_distance = course.distance_m
        distance_tolerance = course_distance * distance_tolerance_pct

        matching = [
            MatchingActivity(
                id=a.id,
                title=a.title,
                started_at=a.started_at,
                total_distance_m=a.total_distance_m or 0,
                moving_time_s=a.moving_time_s or 0,
                avg_power_w=a.avg_power_w,
            )
            for a in activities
            if self._is_matching(a, course_distance, distance_tolerance)
        ]

        return matching[:limit]

    def _is_matching(
        self,
        activity,
        course_distance: float,
        distance_tolerance: float,
    ) -> bool:
        """Check if activity matches the course criteria."""
        if activity.avg_power_w is None or activity.avg_power_w <= 0:
            return False
        if activity.total_distance_m is None:
            return False
        return abs(activity.total_distance_m - course_distance) <= distance_tolerance
