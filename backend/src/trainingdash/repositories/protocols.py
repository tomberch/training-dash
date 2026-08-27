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
        crr: float | None = None,
    ) -> bool:
        """
        Update a bike's CdA and optionally Crr from calibration.

        Sets cda, cda_source='calibrated', and calibrated_at timestamp.
        If crr is provided, also sets crr and crr_source='calibrated'.

        Args:
            bike_id: Bike ID
            user_id: Owner's user ID (for security scoping)
            cda: New CdA value in m²
            crr: New Crr value (optional)

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


class RacePlanRepo(Protocol):
    """
    Repository protocol for RacePlan entities.

    Race plans store generated pacing strategies for courses with
    rider/bike parameters, optimization settings, and segment targets.
    """

    async def get_by_id(self, plan_id: int, user_id: int) -> "RacePlan | None":
        """
        Fetch a race plan by ID, scoped to user.

        Returns None if not found or not owned by user.
        """
        ...

    async def get_by_course(self, course_id: int, user_id: int) -> list["RacePlan"]:
        """
        List race plans for a course, ordered by created_at descending.

        Args:
            course_id: Course ID
            user_id: Owner's user ID

        Returns:
            List of RacePlan objects
        """
        ...

    async def get_by_user(self, user_id: int, limit: int = 20) -> list["RacePlan"]:
        """
        List race plans for a user, ordered by created_at descending.

        Args:
            user_id: Owner's user ID
            limit: Maximum number of plans to return

        Returns:
            List of RacePlan objects
        """
        ...

    async def save(self, plan: "RacePlan") -> "RacePlan":
        """
        Persist a race plan (insert or update).

        Returns the saved plan with any DB-generated fields populated.
        """
        ...

    async def delete(self, plan_id: int, user_id: int) -> bool:
        """
        Delete a race plan.

        Returns True if deleted, False if not found.
        """
        ...


class BackupRepo(Protocol):
    """
    Repository protocol for backup configuration and history.

    Manages the singleton backup configuration and backup history log.
    """

    async def get_config(self) -> "BackupConfig | None":
        """
        Get the backup configuration.

        Returns None if no configuration exists yet.
        """
        ...

    async def save_config(self, config: "BackupConfig") -> "BackupConfig":
        """
        Save backup configuration (upsert).

        Creates the singleton row if it doesn't exist, or updates it.
        Returns the saved config with any DB-generated fields populated.
        """
        ...

    async def upsert_config(
        self,
        *,
        enabled: bool,
        repository_path: str,
        schedule_hour: int | None,
        retention_keep_daily: int,
        retention_keep_weekly: int,
        retention_keep_monthly: int,
    ) -> "BackupConfig":
        """
        Create or update backup configuration from primitive values.

        This is the preferred method for routers to avoid importing models.
        Returns the saved config.
        """
        ...

    async def create_history_entry(
        self,
        trigger_type: str,
        status: str,
        db_migration_version: str | None = None,
    ) -> "BackupHistory":
        """
        Create a new backup history entry.

        Called at backup start with status='running'.
        Returns the created entry with generated ID.
        """
        ...

    async def update_history_entry(
        self,
        entry_id: int,
        *,
        snapshot_id: str | None = None,
        status: str | None = None,
        completed_at: "datetime | None" = None,
        duration_seconds: float | None = None,
        files_new: int | None = None,
        files_changed: int | None = None,
        files_unmodified: int | None = None,
        bytes_added: int | None = None,
        bytes_total: int | None = None,
        error_message: str | None = None,
    ) -> "BackupHistory | None":
        """
        Update a backup history entry.

        Called at backup completion/failure to record results.
        Returns the updated entry, or None if not found.
        """
        ...

    async def get_history(self, limit: int = 20) -> list["BackupHistory"]:
        """
        List backup history entries, most recent first.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of BackupHistory objects ordered by started_at descending
        """
        ...

    async def get_history_entry(self, entry_id: int) -> "BackupHistory | None":
        """
        Get a specific backup history entry by ID.

        Returns None if not found.
        """
        ...

    async def get_latest_completed(self) -> "BackupHistory | None":
        """
        Get the most recent completed backup.

        Returns None if no completed backups exist.
        """
        ...

    async def is_backup_running(self) -> bool:
        """
        Check if a backup is currently running.

        Returns True if there's an entry with status='running'.
        """
        ...

    async def get_migration_version(self) -> str | None:
        """
        Get current alembic migration version from database.

        Returns the version_num from alembic_version table, or None if not found.
        """
        ...


class PacingCoefficientsRepo(Protocol):
    """
    Repository protocol for personalized pacing coefficients.

    Stores per-user and optionally per-bike pacing model coefficients
    learned from actual ride data.

    Fallback chain for get_for_user_bike:
    1. Bike-specific coefficients (if bike_id provided and exists)
    2. User default coefficients (bike_id=NULL)
    3. None (caller should use global defaults)
    """

    async def get_for_user_bike(
        self,
        user_id: int,
        bike_id: int | None = None,
    ) -> "PacingCoefficients | None":
        """
        Get pacing coefficients with fallback chain.

        Tries bike-specific first (if bike_id provided), then user default.
        Returns None if no coefficients found (use global defaults).
        """
        ...

    async def get_user_default(self, user_id: int) -> "PacingCoefficients | None":
        """
        Get user's default coefficients (bike_id=NULL).

        Returns None if not yet created.
        """
        ...

    async def get_for_bike(self, user_id: int, bike_id: int) -> "PacingCoefficients | None":
        """
        Get bike-specific coefficients only (no fallback).

        Returns None if no bike-specific coefficients exist.
        """
        ...

    async def list_for_user(self, user_id: int) -> list["PacingCoefficients"]:
        """
        List all coefficients for a user (default + all bikes).

        Ordered by bike_id (NULL first, then by bike_id).
        """
        ...

    async def save(self, coefficients: "PacingCoefficients") -> "PacingCoefficients":
        """
        Persist coefficients (insert or update).

        Returns the saved coefficients with any DB-generated fields populated.
        """
        ...

    async def upsert(
        self,
        user_id: int,
        bike_id: int | None,
        grade_power_intercept: float,
        grade_power_slope: float,
        max_descent_speed_mps: float,
        descent_power_multiplier: float,
        curvature_speed_coefficient: float,
        climb_sample_count: int,
        descent_sample_count: int,
        activity_count: int,
    ) -> "PacingCoefficients":
        """
        Insert or update coefficients for a user/bike combination.

        Uses ON CONFLICT to atomically upsert.
        """
        ...

    async def delete(self, user_id: int, bike_id: int | None) -> bool:
        """
        Delete coefficients for a user/bike combination.

        Returns True if deleted, False if not found.
        """
        ...


class SegmentRepo(Protocol):
    """
    Repository protocol for Segment entities.

    Segments are globally shared climb/sprint/custom sections of road.
    They can be 'suggested' (auto-detected) or 'approved' (user-confirmed).
    Soft-deleted via deleted_at timestamp.
    """

    async def get_by_id(self, segment_id: UUID) -> "Segment | None":
        """Fetch a segment by ID. Returns None if not found or soft-deleted."""
        ...

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
    ) -> list["Segment"]:
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
        ...

    async def count_approved(
        self,
        type: str | None = None,
        category: list[str] | None = None,
        bounds: tuple[float, float, float, float] | None = None,
        search: str | None = None,
    ) -> int:
        """Count approved segments matching the given filters."""
        ...

    async def save(self, segment: "Segment") -> "Segment":
        """
        Persist a segment (insert or update).

        Returns the saved segment with any DB-generated fields populated.
        """
        ...

    async def soft_delete(self, segment_id: UUID) -> bool:
        """
        Soft-delete a segment by setting deleted_at.

        Returns True if deleted, False if not found.
        """
        ...

    async def find_candidates_for_matching(
        self,
        bounds: "WKBElement",
        direction_bearing: float,
    ) -> list["Segment"]:
        """
        Find approved segments that might match an activity section.

        Uses spatial intersection with bounds and direction within ±60°.

        Args:
            bounds: PostGIS polygon covering the activity section
            direction_bearing: Travel direction in degrees (0-360)

        Returns:
            List of candidate Segment objects for detailed matching
        """
        ...

    async def increment_counts(self, segment_id: UUID, new_athlete: bool) -> None:
        """
        Increment effort_count and optionally athlete_count.

        Args:
            segment_id: Segment to update
            new_athlete: If True, also increment athlete_count
        """
        ...


class SegmentEffortRepo(Protocol):
    """
    Repository protocol for SegmentEffort entities.

    Efforts track a user's completion of a segment during an activity,
    including elapsed time, power, HR, and PR status.
    """

    async def get_by_id(self, effort_id: UUID) -> "SegmentEffort | None":
        """Fetch an effort by ID. Returns None if not found."""
        ...

    async def list_for_segment(
        self,
        segment_id: UUID,
        user_id: int,
        sort: str = "time",
        order: str = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> list["SegmentEffort"]:
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
        ...

    async def list_for_activity(self, activity_id: UUID) -> list["SegmentEffort"]:
        """
        List all efforts from an activity, ordered by start_index.

        Returns:
            List of SegmentEffort objects in ride order
        """
        ...

    async def save(self, effort: "SegmentEffort") -> "SegmentEffort":
        """
        Persist an effort (insert or update).

        Returns the saved effort with any DB-generated fields populated.
        """
        ...

    async def get_user_pr(self, segment_id: UUID, user_id: int) -> "SegmentEffort | None":
        """
        Get the user's PR effort on a segment.

        Returns the effort with is_pr=True, or None if no efforts exist.
        """
        ...

    async def clear_user_pr(self, segment_id: UUID, user_id: int) -> None:
        """
        Clear the is_pr flag on all of a user's efforts for a segment.

        Called before setting a new PR.
        """
        ...


class SegmentSuggestionRepo(Protocol):
    """
    Repository protocol for SegmentSuggestion entities.

    Suggestions track auto-detected segments per user with repetition
    counts and expiration. Users can dismiss suggestions they don't want.
    """

    async def get_by_id(self, suggestion_id: UUID) -> "SegmentSuggestion | None":
        """Fetch a suggestion by ID. Returns None if not found."""
        ...

    async def list_for_user(
        self,
        user_id: int,
        include_dismissed: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list["SegmentSuggestion"]:
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
        ...

    async def count_for_user(self, user_id: int, include_dismissed: bool = False) -> int:
        """Count suggestions for a user."""
        ...

    async def save(self, suggestion: "SegmentSuggestion") -> "SegmentSuggestion":
        """
        Persist a suggestion (insert or update).

        Returns the saved suggestion with any DB-generated fields populated.
        """
        ...

    async def dismiss(self, suggestion_id: UUID) -> bool:
        """
        Dismiss a suggestion by setting dismissed_at.

        Returns True if dismissed, False if not found.
        """
        ...

    async def dismiss_all(self, user_id: int) -> int:
        """
        Dismiss all suggestions for a user.

        Returns the count of suggestions dismissed.
        """
        ...

    async def get_for_user_segment(self, user_id: int, segment_id: UUID) -> "SegmentSuggestion | None":
        """
        Get the suggestion for a specific user/segment pair.

        Returns None if no suggestion exists.
        """
        ...


# Import types for type hints (avoid circular import at runtime)
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geoalchemy2.elements import WKBElement

    from trainingdash.domain.thresholds import ThresholdHistoryEntry, ThresholdValues
    from trainingdash.repositories.postgres.analytics_repo import RecordsView
    from trainingdash.repositories.postgres.models import (
        Activity,
        AppSettings,
        BackupConfig,
        BackupHistory,
        Bike,
        Event,
        FitnessHistory,
        GarminCredentials,
        JournalEntry,
        JournalEntryActivity,
        Notification,
        PacingCoefficients,
        RaceCourse,
        RacePlan,
        RecalculationJob,
        Record,
        RideEvent,
        RideEventLink,
        RideEventMedia,
        Route,
        SavedFilter,
        Segment,
        SegmentEffort,
        SegmentSuggestion,
        User,
        UserOAuthLink,
        XertCredentials,
    )
