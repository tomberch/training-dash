"""In-memory fake implementation of HistoricalNpRepo for testing."""

from trainingdash.domain.historical_np import HistoricalNpStats


class FakeHistoricalNpRepo:
    """
    In-memory fake implementation of HistoricalNpRepo protocol.

    Stores preconfigured course→route mappings and route→stats mappings
    for controlled test scenarios.
    """

    def __init__(self) -> None:
        # Maps (user_id, course_id) → route_id
        self._course_routes: dict[tuple[int, int], int] = {}
        # Maps (user_id, route_id) → HistoricalNpStats
        self._route_stats: dict[tuple[int, int], HistoricalNpStats] = {}

    # --- Protocol methods ---

    async def find_route_for_course(
        self,
        user_id: int,
        course_id: int,
        threshold_m: float = 100.0,
    ) -> int | None:
        """Return preconfigured route ID for the course, or None."""
        return self._course_routes.get((user_id, course_id))

    async def get_stats_for_route(
        self,
        user_id: int,
        route_id: int,
    ) -> HistoricalNpStats | None:
        """Return preconfigured stats for the route, or None."""
        return self._route_stats.get((user_id, route_id))

    async def get_for_course(
        self,
        user_id: int,
        course_id: int,
    ) -> HistoricalNpStats | None:
        """Combine route lookup and stats lookup."""
        route_id = await self.find_route_for_course(user_id, course_id)
        if route_id is None:
            return None
        return await self.get_stats_for_route(user_id, route_id)

    # --- Test helper methods ---

    def set_course_route(self, user_id: int, course_id: int, route_id: int) -> None:
        """Configure a course to match a specific route."""
        self._course_routes[(user_id, course_id)] = route_id

    def set_route_stats(self, user_id: int, route_id: int, stats: HistoricalNpStats) -> None:
        """Configure stats for a specific route."""
        self._route_stats[(user_id, route_id)] = stats

    def clear(self) -> None:
        """Clear all configured data."""
        self._course_routes.clear()
        self._route_stats.clear()
