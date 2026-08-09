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


class XertCredentialsRepo(Protocol):
    """
    Repository protocol for Xert integration credentials.
    """

    async def get_by_user_id(self, user_id: int) -> "XertCredentials | None":
        """Fetch Xert credentials for a user. Returns None if not configured."""
        ...

    async def exists(self, user_id: int) -> bool:
        """Check if user has Xert credentials configured."""
        ...

    async def save(
        self,
        user_id: int,
        xert_email: str,
        encrypted_password: str,
        sync_since: "datetime | None" = None,
    ) -> "XertCredentials":
        """
        Upsert Xert credentials for a user.

        Returns the saved credentials.
        """
        ...

    async def delete(self, user_id: int) -> bool:
        """
        Delete Xert credentials for a user.

        Returns True if deleted, False if not found.
        """
        ...


class GarminCredentialsRepo(Protocol):
    """
    Repository protocol for Garmin integration credentials.
    """

    async def get_by_user_id(self, user_id: int) -> "GarminCredentials | None":
        """Fetch Garmin credentials for a user. Returns None if not configured."""
        ...

    async def exists(self, user_id: int) -> bool:
        """Check if user has Garmin credentials configured."""
        ...

    async def save(
        self,
        user_id: int,
        garmin_email: str,
        encrypted_password: str,
        sync_since: "datetime | None" = None,
    ) -> "GarminCredentials":
        """
        Upsert Garmin credentials for a user.

        Returns the saved credentials.
        """
        ...

    async def delete(self, user_id: int) -> bool:
        """
        Delete Garmin credentials for a user.

        Returns True if deleted, False if not found.
        """
        ...


class NotificationRepo(Protocol):
    """
    Repository protocol for user notifications.
    """

    async def list_for_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list["Notification"]:
        """List notifications for a user, ordered by created_at descending."""
        ...

    async def get_by_id(self, notification_id: UUID, user_id: int) -> "Notification | None":
        """Fetch a notification by ID, scoped to user."""
        ...

    async def mark_read(self, notification_id: UUID, user_id: int) -> bool:
        """Mark a notification as read. Returns True if updated, False if not found."""
        ...

    async def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        ...


class AppSettingsRepo(Protocol):
    """
    Repository protocol for application settings.
    """

    async def get(self, key: str) -> str | None:
        """Get a setting value by key. Returns None if not set."""
        ...

    async def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean setting. Returns default if not set."""
        ...

    async def set(self, key: str, value: str) -> None:
        """Set a setting value (upsert)."""
        ...

    async def list_all(self) -> list["AppSettings"]:
        """List all settings."""
        ...


class AuditLogRepo(Protocol):
    """
    Repository protocol for audit log entries.
    """

    async def log(
        self,
        admin_id: int,
        action: str,
        target_user_id: int | None = None,
        details: str | None = None,
    ) -> None:
        """Record an audit log entry."""
        ...


class RecalculationJobRepo(Protocol):
    """
    Repository protocol for metric recalculation jobs.
    """

    async def get_by_user_id(self, user_id: int) -> "RecalculationJob | None":
        """Get the recalculation job for a user."""
        ...

    async def upsert_pending(self, user_id: int) -> "RecalculationJob":
        """Create or update job to pending status."""
        ...

    async def upsert_failed(self, user_id: int) -> "RecalculationJob":
        """Create or update job to failed status."""
        ...

    async def mark_running(self, user_id: int) -> None:
        """Mark job as running."""
        ...

    async def mark_completed(self, user_id: int, activities_updated: int) -> None:
        """Mark job as completed with count of updated activities."""
        ...

    async def mark_failed(self, user_id: int, error_message: str) -> None:
        """Mark job as failed with error message."""
        ...


class OAuthLinkRepo(Protocol):
    """
    Repository protocol for OAuth provider links.
    """

    async def get_by_provider_id(self, provider: str, provider_user_id: str) -> "UserOAuthLink | None":
        """Find a link by provider and provider's user ID."""
        ...

    async def list_for_user(self, user_id: int) -> list["UserOAuthLink"]:
        """List all OAuth links for a user."""
        ...

    async def get_for_user(self, user_id: int, provider: str) -> "UserOAuthLink | None":
        """Get a specific OAuth link for a user and provider."""
        ...

    async def save(
        self,
        user_id: int,
        provider: str,
        provider_user_id: str,
        provider_email: str | None = None,
    ) -> "UserOAuthLink":
        """Create or update an OAuth link."""
        ...

    async def delete(self, user_id: int, provider: str) -> bool:
        """Delete an OAuth link. Returns True if deleted."""
        ...

    async def count_for_user(self, user_id: int) -> int:
        """Count OAuth links for a user."""
        ...


class RouteRepo(Protocol):
    """
    Repository protocol for Route entities.

    Note: Complex spatial operations (find_or_create with Hausdorff distance)
    remain in route_matching.py due to PostGIS dependency. This protocol
    covers simpler route operations.
    """

    async def get_by_id(self, route_id: int) -> "Route | None":
        """Fetch a route by ID."""
        ...

    async def list_for_user(self, user_id: int) -> list["Route"]:
        """List all routes for a user, ordered by ride_count descending."""
        ...

    async def increment_ride_count(self, route_id: int) -> None:
        """Increment the ride count for a route."""
        ...

    async def decrement_ride_count(self, route_id: int) -> None:
        """Decrement the ride count for a route."""
        ...

    async def delete(self, route_id: int) -> bool:
        """Delete a route. Returns True if deleted."""
        ...


class GeocodingCacheRepo(Protocol):
    """
    Repository protocol for geocoding cache entries.

    Caches reverse geocoding results to respect OpenStreetMap/Photon rate limits.
    """

    async def get(self, cache_key: str) -> str | None:
        """
        Get cached geocoding result by key.

        Returns JSON string if found, None if not cached.
        """
        ...

    async def set(self, cache_key: str, result_json: str) -> None:
        """
        Store geocoding result in cache.

        Upserts the entry (inserts or updates if key exists).
        """
        ...


class AnalyticsRepo(Protocol):
    """
    Read-only repository protocol for analytics / dashboard queries.

    All methods are read-only (no commits). The router serializes the ORM
    objects returned, with the exception of ``get_records`` which returns a
    typed ``RecordsView`` composite.
    """

    async def get_latest_fitness(self, user_id: int) -> "FitnessHistory | None":
        """Most recent fitness snapshot for the user, or None."""
        ...

    async def get_fitness_history(
        self, user_id: int, limit: int = 10
    ) -> "list[FitnessHistory]":
        """Recent fitness snapshots, most recent first."""
        ...

    async def list_activities_for_pmc(self, user_id: int) -> "list[Activity]":
        """All activities for the user, ordered by started_at ASC."""
        ...

    async def get_power_curve(
        self,
        user_id: int,
        start: "date | None" = None,
        end: "date | None" = None,
    ) -> "list[Any]":
        """Peak powers joined with activity start time, date-filtered."""
        ...

    async def get_records(self, user_id: int) -> "RecordsView":
        """Lifetime + per-route PRs as a composite view."""
        ...


# Import types for type hints (avoid circular import at runtime)
from datetime import date, datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from trainingdash.repositories.postgres.analytics_repo import RecordsView
    from trainingdash.repositories.postgres.models import (
        Activity,
        AppSettings,
        FitnessHistory,
        GarminCredentials,
        Notification,
        RecalculationJob,
        Route,
        User,
        UserOAuthLink,
        XertCredentials,
    )
