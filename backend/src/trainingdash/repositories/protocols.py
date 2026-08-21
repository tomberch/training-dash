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
        activity_type: str | None = None,
    ) -> list[Activity]:
        """
        List activities for a user, ordered by started_at descending.

        Args:
            user_id: Owner's user ID
            limit: Maximum number of activities to return
            offset: Number of activities to skip (for pagination)
            activity_type: Filter by activity type (None = all, empty string = unclassified)

        Returns:
            List of Activity objects
        """
        ...

    async def count_for_user(self, user_id: int, activity_type: str | None = None) -> int:
        """Count total activities for a user, optionally filtered by type."""
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

    async def list_by_bike(
        self,
        bike_id: int,
        user_id: int,
        limit: int = 50,
    ) -> list[Activity]:
        """
        List activities tagged to a specific bike for a user.

        Args:
            bike_id: Bike ID to filter by
            user_id: Owner's user ID
            limit: Maximum number of activities to return

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

    async def update_sync_enabled(self, user_id: int, sync_enabled: bool) -> bool:
        """
        Update the sync_enabled flag for a user's Xert credentials.

        Returns True if updated, False if credentials not found.
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

    async def update_sync_enabled(self, user_id: int, sync_enabled: bool) -> bool:
        """
        Update the sync_enabled flag for a user's Garmin credentials.

        Returns True if updated, False if credentials not found.
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


class ThresholdRepo(Protocol):
    """
    Repository protocol for threshold metric entries (FTP, LTHR, HRmax).

    All methods are read-only or flush-only; the caller owns the transaction.
    """

    async def get_for_date(self, user_id: int, target_date: "date") -> "ThresholdValues":
        """Threshold values (FTP, LTHR, HRmax) effective on ``target_date``."""
        ...

    async def get_history(self, user_id: int) -> "list[ThresholdHistoryEntry]":
        """All threshold entries, grouped by effective_date (descending)."""
        ...

    async def create(
        self,
        user_id: int,
        effective_date: "date",
        ftp_watts: int | None = None,
        lthr_bpm: int | None = None,
        hrmax_bpm: int | None = None,
        source: str = "manual",
        source_detail: str | None = None,
    ) -> None:
        """Create threshold entries for the provided values. Flushes; caller commits."""
        ...

    async def has_any_threshold(self, user_id: int) -> bool:
        """True if the user has at least one FTP threshold entry."""
        ...


class EventRepo(Protocol):
    """
    Repository protocol for system events.

    Events are logged for observability on the Admin System Dashboard.
    They capture activity lifecycle, sync operations, job outcomes, etc.
    """

    async def log(
        self,
        event_type: str,
        outcome: str,
        user_id: int | None = None,
        payload: dict | None = None,
    ) -> int:
        """
        Log an event to the system event log.

        Args:
            event_type: Event type (e.g., 'sync.completed', 'activity.ingested')
            outcome: Event outcome ('success', 'failure', 'info')
            user_id: Optional user ID (None for system-wide events)
            payload: Optional JSON-serializable payload with event-specific data

        Returns:
            The ID of the created event.
        """
        ...

    async def list(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: "datetime | None" = None,
        until: "datetime | None" = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list["Event"]:
        """
        List events with optional filters.

        Args:
            event_type: Filter by exact event type
            outcome: Filter by outcome
            user_id: Filter by user ID
            since: Filter events created after this time
            until: Filter events created before this time
            limit: Maximum number of events to return (max 100)
            offset: Number of events to skip (for pagination)

        Returns:
            List of Event objects, ordered by created_at descending.
        """
        ...

    async def count(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: "datetime | None" = None,
        until: "datetime | None" = None,
    ) -> int:
        """
        Count events matching the given filters.

        Same filter parameters as list().
        """
        ...

    async def delete_before(self, cutoff: "datetime", batch_size: int = 1000) -> int:
        """
        Delete events older than the cutoff time.

        Deletes in batches to avoid long locks.

        Args:
            cutoff: Delete events with created_at < cutoff
            batch_size: Number of events to delete per batch

        Returns:
            Total number of events deleted.
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

    async def get_fitness_history(self, user_id: int, limit: int = 10) -> "list[FitnessHistory]":
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


class SavedFilterRepo(Protocol):
    """
    Repository protocol for saved query filters.

    Users can save queries for reuse across sessions. Each filter has a unique
    name per user. One filter can be marked as default.
    """

    async def get_by_id(self, filter_id: int, user_id: int) -> "SavedFilter | None":
        """Fetch a saved filter by ID, scoped to user. Returns None if not found."""
        ...

    async def get_by_name(self, name: str, user_id: int) -> "SavedFilter | None":
        """Fetch a saved filter by name, scoped to user. Returns None if not found."""
        ...

    async def list_for_user(self, user_id: int) -> list["SavedFilter"]:
        """List all saved filters for a user, ordered by name."""
        ...

    async def get_default(self, user_id: int) -> "SavedFilter | None":
        """Get the user's default filter, if any."""
        ...

    async def create(
        self,
        user_id: int,
        name: str,
        query_text: str,
        description: str | None = None,
        is_default: bool = False,
    ) -> "SavedFilter":
        """
        Create a new saved filter. Validates the query before saving.

        If is_default=True, clears any existing default for the user.

        Returns the created filter.
        """
        ...

    async def update(
        self,
        filter_id: int,
        user_id: int,
        name: str | None = None,
        query_text: str | None = None,
        description: str | None = None,
        is_default: bool | None = None,
    ) -> "SavedFilter | None":
        """
        Update an existing saved filter. Validates query if changed.

        If is_default=True, clears any existing default for the user.

        Returns the updated filter, or None if not found.
        """
        ...

    async def delete(self, filter_id: int, user_id: int) -> bool:
        """Delete a saved filter. Returns True if deleted, False if not found."""
        ...

    async def set_default(self, filter_id: int, user_id: int) -> bool:
        """Set a filter as the user's default (clears existing default). Returns True if set."""
        ...

    async def clear_default(self, user_id: int) -> None:
        """Clear the user's default filter (no filter is default)."""
        ...


class RideEventRepo(Protocol):
    """
    Repository protocol for RideEvent entities.

    RideEvents represent user-curated events (races, tours, trips) that
    group activities with journal entries, media, and links.
    """

    async def get_by_id(self, event_id: UUID, user_id: int) -> "RideEvent | None":
        """
        Fetch a ride event by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        ...

    async def list_for_user(
        self,
        user_id: int,
        event_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list["RideEvent"]:
        """
        List ride events for a user, ordered by start_date descending.

        Args:
            user_id: Owner's user ID
            event_type: Optional filter by event type
            limit: Maximum number of events to return
            offset: Number of events to skip (for pagination)
        """
        ...

    async def count_for_user(self, user_id: int, event_type: str | None = None) -> int:
        """Count total ride events for a user, optionally filtered by type."""
        ...

    async def save(self, event: "RideEvent") -> "RideEvent":
        """
        Persist a ride event (insert or update).

        Returns the saved event with any DB-generated fields populated.
        """
        ...

    async def delete(self, event_id: UUID, user_id: int) -> bool:
        """
        Delete a ride event owned by the given user.

        Cascade deletes journal entries, media, links. Unlinks activities.

        Returns True if deleted, False if not found.
        """
        ...


class JournalEntryRepo(Protocol):
    """
    Repository protocol for JournalEntry entities.

    Journal entries are day-by-day records within a ride event.
    """

    async def get_by_id(self, entry_id: UUID, user_id: int) -> "JournalEntry | None":
        """
        Fetch a journal entry by ID, scoped to user (via event ownership).

        Returns None if not found or event not owned by user.
        """
        ...

    async def list_for_event(self, event_id: UUID) -> list["JournalEntry"]:
        """
        List journal entries for an event, ordered by entry_date ascending.
        """
        ...

    async def save(self, entry: "JournalEntry") -> "JournalEntry":
        """
        Persist a journal entry (insert or update).

        Returns the saved entry with any DB-generated fields populated.
        """
        ...

    async def delete(self, entry_id: UUID, user_id: int) -> bool:
        """
        Delete a journal entry (user must own the parent event).

        Returns True if deleted, False if not found.
        """
        ...


class RideEventMediaRepo(Protocol):
    """
    Repository protocol for RideEventMedia entities.

    Media (photos, video embeds) attached to events or journal entries.
    """

    async def get_by_id(self, media_id: UUID, user_id: int) -> "RideEventMedia | None":
        """
        Fetch media by ID, scoped to user (via event/entry ownership).

        Returns None if not found or not accessible by user.
        """
        ...

    async def list_for_event(self, event_id: UUID) -> list["RideEventMedia"]:
        """List all media directly attached to an event (not entries)."""
        ...

    async def list_for_entry(self, entry_id: UUID) -> list["RideEventMedia"]:
        """List all media attached to a journal entry."""
        ...

    async def save(self, media: "RideEventMedia") -> "RideEventMedia":
        """Persist media (insert or update)."""
        ...

    async def delete(self, media_id: UUID, user_id: int) -> bool:
        """Delete media. Returns True if deleted, False if not found."""
        ...


class RideEventLinkRepo(Protocol):
    """
    Repository protocol for RideEventLink entities.

    External links attached to events or journal entries.
    """

    async def get_by_id(self, link_id: UUID, user_id: int) -> "RideEventLink | None":
        """
        Fetch link by ID, scoped to user (via event/entry ownership).

        Returns None if not found or not accessible by user.
        """
        ...

    async def list_for_event(self, event_id: UUID) -> list["RideEventLink"]:
        """List all links directly attached to an event (not entries)."""
        ...

    async def list_for_entry(self, entry_id: UUID) -> list["RideEventLink"]:
        """List all links attached to a journal entry."""
        ...

    async def save(self, link: "RideEventLink") -> "RideEventLink":
        """Persist link (insert or update)."""
        ...

    async def delete(self, link_id: UUID, user_id: int) -> bool:
        """Delete link. Returns True if deleted, False if not found."""
        ...


class JournalEntryActivityRepo(Protocol):
    """
    Repository protocol for JournalEntryActivity join table.

    Links activities to journal entries within an event.
    """

    async def list_for_entry(self, entry_id: UUID) -> list["JournalEntryActivity"]:
        """List activity links for a journal entry, ordered by sort_order."""
        ...

    async def list_for_event(self, event_id: UUID) -> list["JournalEntryActivity"]:
        """List all activity links across all entries in an event."""
        ...

    async def link(self, entry_id: UUID, activity_id: UUID, sort_order: int = 0) -> "JournalEntryActivity":
        """Link an activity to a journal entry."""
        ...

    async def unlink(self, entry_id: UUID, activity_id: UUID) -> bool:
        """Unlink an activity from a journal entry. Returns True if unlinked."""
        ...

    async def reorder(self, entry_id: UUID, activity_ids: list[UUID]) -> None:
        """Reorder activities in an entry based on the provided ID list."""
        ...


class CourseRepo(Protocol):
    """
    Repository protocol for RaceCourse entities.

    Courses represent race/event courses for pacing optimization.
    Each user can have multiple courses imported from GPX/FIT files.
    """

    async def get_by_id(self, course_id: int, user_id: int) -> "RaceCourse | None":
        """
        Fetch a course by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        ...

    async def get_by_user(self, user_id: int) -> list["RaceCourse"]:
        """
        List courses for a user, ordered by created_at descending.

        Returns:
            List of RaceCourse objects
        """
        ...

    async def save(self, course: "RaceCourse") -> "RaceCourse":
        """
        Persist a course (insert or update).

        Returns the saved course with any DB-generated fields populated.
        """
        ...

    async def delete(self, course_id: int, user_id: int) -> bool:
        """
        Delete a course.

        Returns True if deleted, False if not found.
        """
        ...

    async def update_processed_data(
        self,
        course_id: int,
        user_id: int,
        elevation_profile: list[dict],
        segments: list[dict],
        climbs: list[dict],
    ) -> None:
        """
        Update the processed data for a course.

        Args:
            course_id: Course ID
            user_id: Owner's user ID (for security scoping)
            elevation_profile: List of {distance_m, elevation_m, grade_pct}
            segments: List of {start_m, end_m, avg_grade_pct, distance_m, ...}
            climbs: List of {name, start_m, end_m, avg_grade_pct, category, ...}
        """
        ...


class BikeRepo(Protocol):
    """
    Repository protocol for Bike entities.

    Bikes represent user equipment for CdA/Crr calibration and race planning.
    Each user can have multiple bikes with one optional default.
    """

    async def get_by_id(self, bike_id: int, user_id: int) -> "Bike | None":
        """
        Fetch a bike by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        ...

    async def get_by_user(self, user_id: int, include_retired: bool = False) -> list["Bike"]:
        """
        List bikes for a user, ordered by name.

        Args:
            user_id: Owner's user ID
            include_retired: If True, include retired bikes

        Returns:
            List of Bike objects
        """
        ...

    async def get_default_for_user(self, user_id: int) -> "Bike | None":
        """
        Get the user's default bike.

        Returns None if no default bike is set or if the default is retired.
        """
        ...

    async def save(self, bike: "Bike") -> "Bike":
        """
        Persist a bike (insert or update).

        Returns the saved bike with any DB-generated fields populated.
        """
        ...

    async def update_distance(self, bike_id: int, user_id: int, delta_m: float) -> None:
        """
        Update a bike's total_distance_m by adding delta_m.

        Args:
            bike_id: Bike ID
            user_id: Owner's user ID (for security scoping)
            delta_m: Distance to add (can be negative for corrections)
        """
        ...

    async def set_default(self, user_id: int, bike_id: int) -> None:
        """
        Set a bike as the user's default.

        Clears any existing default for the user first.
        The bike must be non-retired and owned by the user.
        """
        ...

    async def clear_default(self, user_id: int) -> None:
        """
        Clear the user's default bike (no bike is default).
        """
        ...

    async def retire(self, bike_id: int, user_id: int) -> bool:
        """
        Retire a bike (soft delete).

        Sets retired_at timestamp. If the bike was default, clears default.

        Returns True if retired, False if not found.
        """
        ...

    async def update_calibration(
        self,
        bike_id: int,
        user_id: int,
        cda: float,
    ) -> bool:
        """
        Update a bike's CdA from calibration.

        Sets cda, cda_source='calibrated', and calibrated_at timestamp.

        Args:
            bike_id: Bike ID
            user_id: Owner's user ID (for security scoping)
            cda: New CdA value in m²

        Returns:
            True if updated, False if bike not found.
        """
        ...


class RecordRepo(Protocol):
    """
    Repository protocol for activity Record entities.

    Records are per-second data points within an activity (power, speed, etc.).
    """

    async def list_for_activity(self, activity_id: "UUID") -> list["Record"]:
        """
        List all records for an activity, ordered by timestamp.

        Args:
            activity_id: Activity UUID

        Returns:
            List of Record objects ordered by timestamp ascending
        """
        ...


# Import types for type hints (avoid circular import at runtime)
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from trainingdash.domain.thresholds import ThresholdHistoryEntry, ThresholdValues
    from trainingdash.repositories.postgres.analytics_repo import RecordsView
    from trainingdash.repositories.postgres.models import (
        Activity,
        AppSettings,
        Bike,
        Event,
        FitnessHistory,
        GarminCredentials,
        JournalEntry,
        JournalEntryActivity,
        Notification,
        RaceCourse,
        RecalculationJob,
        Record,
        RideEvent,
        RideEventLink,
        RideEventMedia,
        Route,
        SavedFilter,
        User,
        UserOAuthLink,
        XertCredentials,
    )
