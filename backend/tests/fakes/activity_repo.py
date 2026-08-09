"""In-memory fake implementation of ActivityRepo for testing."""

from uuid import UUID

from trainingdash.repositories.postgres.models import Activity


class FakeActivityRepo:
    """
    In-memory fake implementation of ActivityRepo protocol.
    
    Stores activities in a dict keyed by (user_id, activity_id).
    Provides inspection methods for test assertions.
    """

    def __init__(self) -> None:
        self._activities: dict[tuple[int, UUID], Activity] = {}

    # --- Protocol methods ---

    async def get_by_id(self, activity_id: UUID, user_id: int) -> Activity | None:
        return self._activities.get((user_id, activity_id))

    async def list_for_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Activity]:
        user_activities = [
            a for (uid, _), a in self._activities.items() if uid == user_id
        ]
        # Sort by started_at descending
        user_activities.sort(key=lambda a: a.started_at or 0, reverse=True)
        return user_activities[offset : offset + limit]

    async def count_for_user(self, user_id: int) -> int:
        return sum(1 for (uid, _) in self._activities if uid == user_id)

    async def save(self, activity: Activity) -> Activity:
        if activity.user_id is None:
            raise ValueError("Activity must have a user_id")
        self._activities[(activity.user_id, activity.id)] = activity
        return activity

    async def delete(self, activity_id: UUID, user_id: int) -> bool:
        key = (user_id, activity_id)
        if key in self._activities:
            del self._activities[key]
            return True
        return False

    async def list_by_route(
        self,
        route_id: int,
        user_id: int,
        exclude_activity_id: UUID | None = None,
    ) -> list[Activity]:
        results = [
            a
            for (uid, aid), a in self._activities.items()
            if uid == user_id
            and a.route_id == route_id
            and (exclude_activity_id is None or aid != exclude_activity_id)
        ]
        results.sort(key=lambda a: a.started_at or 0, reverse=True)
        return results

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored activities."""
        self._activities.clear()

    def all(self) -> list[Activity]:
        """Return all stored activities (for test assertions)."""
        return list(self._activities.values())
