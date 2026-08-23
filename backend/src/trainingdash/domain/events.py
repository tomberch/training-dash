"""
Event type definitions for the system event log.

This module defines the canonical event types and outcomes for the Admin
System Dashboard. Events are emitted from various parts of the codebase
to provide visibility into background operations.

Event types follow a `domain.action` naming convention.
"""

from enum import StrEnum


class EventOutcome(StrEnum):
    """Possible outcomes for an event."""

    SUCCESS = "success"
    FAILURE = "failure"
    INFO = "info"


class EventType(StrEnum):
    """
    Canonical event types for the system event log.

    Organized by domain:
    - activity: Activity lifecycle events
    - sync: Provider sync operations
    - route: Route matching
    - threshold: Threshold/zone changes
    - recalculation: Metric recalculation jobs
    - credentials: Integration credentials
    - breakthrough: Power breakthroughs
    - job: SAQ job outcomes
    - admin: Admin actions (nukes)
    - scheduler: Cron scheduler events
    - cache: Cache maintenance
    """

    # Activity lifecycle
    ACTIVITY_INGESTED = "activity.ingested"
    ACTIVITY_DELETED = "activity.deleted"

    # Sync operations (legacy - kept for backward compatibility)
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"

    # Import operations (preferred naming)
    IMPORT_STARTED = "import.started"
    IMPORT_COMPLETED = "import.completed"

    # Route matching
    ROUTE_MATCHED = "route.matched"

    # Threshold & Recalculation
    THRESHOLD_UPDATED = "threshold.updated"
    RECALCULATION_STARTED = "recalculation.started"
    RECALCULATION_COMPLETED = "recalculation.completed"

    # Credentials / Integrations
    CREDENTIALS_SAVED = "credentials.saved"
    CREDENTIALS_REMOVED = "credentials.removed"
    CREDENTIALS_VALIDATION_FAILED = "credentials.validation_failed"

    # Breakthrough detection
    BREAKTHROUGH_DETECTED = "breakthrough.detected"

    # Job outcomes (SAQ)
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    # Admin actions
    ADMIN_NUKE_ACTIVITIES = "admin.nuke_activities"
    ADMIN_NUKE_INTEGRATIONS = "admin.nuke_integrations"
    ADMIN_NUKE_ACCOUNT = "admin.nuke_account"
    ADMIN_WEATHER_BACKFILL = "admin.weather_backfill"

    # Scheduler
    SCHEDULER_TRIGGERED = "scheduler.triggered"

    # Cache maintenance
    CACHE_PRUNED = "cache.pruned"

    @property
    def domain(self) -> str:
        """Extract the domain from the event type (e.g., 'sync' from 'sync.completed')."""
        return self.value.split(".")[0]

    @property
    def action(self) -> str:
        """Extract the action from the event type (e.g., 'completed' from 'sync.completed')."""
        return self.value.split(".")[1]


# Valid outcomes by event type (for validation)
# Events can have specific valid outcomes, not all three
EVENT_VALID_OUTCOMES: dict[EventType, set[EventOutcome]] = {
    # Activity lifecycle
    EventType.ACTIVITY_INGESTED: {EventOutcome.SUCCESS, EventOutcome.FAILURE},
    EventType.ACTIVITY_DELETED: {EventOutcome.INFO},
    # Sync operations (legacy)
    EventType.SYNC_STARTED: {EventOutcome.INFO},
    EventType.SYNC_COMPLETED: {EventOutcome.SUCCESS, EventOutcome.FAILURE},
    # Import operations
    EventType.IMPORT_STARTED: {EventOutcome.INFO},
    EventType.IMPORT_COMPLETED: {EventOutcome.SUCCESS, EventOutcome.FAILURE},
    # Route matching
    EventType.ROUTE_MATCHED: {EventOutcome.SUCCESS, EventOutcome.FAILURE},
    # Threshold & Recalculation
    EventType.THRESHOLD_UPDATED: {EventOutcome.INFO},
    EventType.RECALCULATION_STARTED: {EventOutcome.INFO},
    EventType.RECALCULATION_COMPLETED: {EventOutcome.SUCCESS, EventOutcome.FAILURE},
    # Credentials
    EventType.CREDENTIALS_SAVED: {EventOutcome.INFO},
    EventType.CREDENTIALS_REMOVED: {EventOutcome.INFO},
    EventType.CREDENTIALS_VALIDATION_FAILED: {EventOutcome.FAILURE},
    # Breakthrough
    EventType.BREAKTHROUGH_DETECTED: {EventOutcome.INFO},
    # Job outcomes
    EventType.JOB_COMPLETED: {EventOutcome.SUCCESS},
    EventType.JOB_FAILED: {EventOutcome.FAILURE},
    # Admin actions
    EventType.ADMIN_NUKE_ACTIVITIES: {EventOutcome.INFO},
    EventType.ADMIN_NUKE_INTEGRATIONS: {EventOutcome.INFO},
    EventType.ADMIN_NUKE_ACCOUNT: {EventOutcome.INFO},
    # Scheduler
    EventType.SCHEDULER_TRIGGERED: {EventOutcome.INFO},
    # Cache
    EventType.CACHE_PRUNED: {EventOutcome.INFO},
}


def validate_event(event_type: EventType, outcome: EventOutcome) -> bool:
    """
    Validate that the outcome is valid for the given event type.

    Returns True if valid, False otherwise.
    """
    valid_outcomes = EVENT_VALID_OUTCOMES.get(event_type)
    if valid_outcomes is None:
        return False
    return outcome in valid_outcomes
