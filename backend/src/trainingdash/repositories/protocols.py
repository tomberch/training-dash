"""
Repository protocols — abstract interfaces for data access.

These protocols define the contract that repository implementations must fulfill.
Use cases depend on these protocols, not on concrete implementations,
enabling testing with in-memory fakes.

Concrete implementations:
- postgres/: PostgreSQL implementations using SQLAlchemy
- tests/fakes/: In-memory fakes for unit testing
"""

from typing import Protocol
from uuid import UUID

from trainingdash.repositories.postgres.models import Activity


class ActivityRepo(Protocol):
    """
    Repository protocol for Activity entities.

    All methods that modify data are assumed to handle their own commits
    or work within an externally-managed transaction scope.
    """

    async def get_by_id(self, activity_id: UUID, user_id: int) -> Activity | None:
        """
        Fetch an activity by ID, scoped to the given user.

        Returns None if not found or not owned by user.
        """
        ...

    async def list_for_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Activity]:
        """
        List activities for a user, ordered by started_at descending.

        Args:
            user_id: Owner's user ID
            limit: Maximum number of activities to return
            offset: Number of activities to skip (for pagination)

        Returns:
            List of Activity objects
        """
        ...

    async def count_for_user(self, user_id: int) -> int:
        """Count total activities for a user."""
        ...

    async def save(self, activity: Activity) -> Activity:
        """
        Persist an activity (insert or update).

        Returns the saved activity with any DB-generated fields populated.
        """
        ...

    async def delete(self, activity_id: UUID, user_id: int) -> bool:
        """
        Delete an activity owned by the given user.

        Handles cascade cleanup (records, laps, peaks) and route maintenance.

        Returns True if deleted, False if not found.
        """
        ...

    async def list_by_route(
        self,
        route_id: int,
        user_id: int,
        exclude_activity_id: UUID | None = None,
    ) -> list[Activity]:
        """
        List activities on a specific route for a user.

        Args:
            route_id: Route ID to filter by
            user_id: Owner's user ID
            exclude_activity_id: Optional activity ID to exclude from results

        Returns:
            List of Activity objects ordered by started_at descending
        """
        ...




class UserRepo(Protocol):
    """
    Repository protocol for User entities.

    All methods that modify data are assumed to handle their own commits
    or work within an externally-managed transaction scope.
    """

    async def get_by_id(self, user_id: int) -> "User | None":
        """Fetch a user by ID. Returns None if not found."""
        ...

    async def get_by_email(self, email: str) -> "User | None":
        """Fetch a user by email (case-insensitive). Returns None if not found."""
        ...

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with the given email exists."""
        ...

    async def list_all(self) -> list["User"]:
        """List all users ordered by ID."""
        ...

    async def list_pending_approval(self) -> list["User"]:
        """List all users pending approval, ordered by created_at."""
        ...

    async def count(self) -> int:
        """Count total users."""
        ...

    async def save(self, user: "User") -> "User":
        """
        Persist a user (insert or update).

        Returns the saved user with any DB-generated fields populated.
        """
        ...

    async def delete(self, user_id: int) -> bool:
        """
        Delete a user by ID.

        Returns True if deleted, False if not found.
        """
        ...


# Import User for type hints (avoid circular import at runtime)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trainingdash.repositories.postgres.models import User
