"""Unit tests for event type definitions."""

from trainingdash.domain.events import (
    EVENT_VALID_OUTCOMES,
    EventOutcome,
    EventType,
    validate_event,
)


class TestEventOutcome:
    """Tests for EventOutcome enum."""

    def test_success_value(self):
        """SUCCESS has expected string value."""
        assert EventOutcome.SUCCESS.value == "success"

    def test_failure_value(self):
        """FAILURE has expected string value."""
        assert EventOutcome.FAILURE.value == "failure"

    def test_info_value(self):
        """INFO has expected string value."""
        assert EventOutcome.INFO.value == "info"

    def test_all_outcomes_are_strings(self):
        """All outcomes should be string enums."""
        for outcome in EventOutcome:
            assert isinstance(outcome.value, str)


class TestEventType:
    """Tests for EventType enum."""

    def test_activity_ingested_value(self):
        """ACTIVITY_INGESTED follows domain.action naming."""
        assert EventType.ACTIVITY_INGESTED.value == "activity.ingested"

    def test_sync_completed_value(self):
        """SYNC_COMPLETED follows domain.action naming."""
        assert EventType.SYNC_COMPLETED.value == "sync.completed"

    def test_domain_property(self):
        """domain property extracts first part."""
        assert EventType.ACTIVITY_INGESTED.domain == "activity"
        assert EventType.SYNC_COMPLETED.domain == "sync"
        assert EventType.ROUTE_MATCHED.domain == "route"
        assert EventType.THRESHOLD_UPDATED.domain == "threshold"

    def test_action_property(self):
        """action property extracts second part."""
        assert EventType.ACTIVITY_INGESTED.action == "ingested"
        assert EventType.SYNC_COMPLETED.action == "completed"
        assert EventType.ROUTE_MATCHED.action == "matched"
        assert EventType.THRESHOLD_UPDATED.action == "updated"

    def test_all_event_types_have_domain_action_format(self):
        """All event types should follow domain.action naming."""
        for event_type in EventType:
            assert "." in event_type.value, f"{event_type} missing dot separator"
            parts = event_type.value.split(".")
            assert len(parts) == 2, f"{event_type} should have exactly one dot"
            assert len(parts[0]) > 0, f"{event_type} has empty domain"
            assert len(parts[1]) > 0, f"{event_type} has empty action"

    def test_all_event_types_have_valid_outcomes_defined(self):
        """Every event type should have valid outcomes defined."""
        for event_type in EventType:
            assert event_type in EVENT_VALID_OUTCOMES, f"{event_type} missing from EVENT_VALID_OUTCOMES"
            assert len(EVENT_VALID_OUTCOMES[event_type]) > 0, f"{event_type} has no valid outcomes"


class TestEventValidOutcomes:
    """Tests for EVENT_VALID_OUTCOMES mapping."""

    def test_activity_ingested_outcomes(self):
        """ACTIVITY_INGESTED can succeed or fail."""
        valid = EVENT_VALID_OUTCOMES[EventType.ACTIVITY_INGESTED]
        assert EventOutcome.SUCCESS in valid
        assert EventOutcome.FAILURE in valid
        assert EventOutcome.INFO not in valid

    def test_activity_deleted_outcomes(self):
        """ACTIVITY_DELETED is info only."""
        valid = EVENT_VALID_OUTCOMES[EventType.ACTIVITY_DELETED]
        assert EventOutcome.INFO in valid
        assert EventOutcome.SUCCESS not in valid
        assert EventOutcome.FAILURE not in valid

    def test_sync_started_outcomes(self):
        """SYNC_STARTED is info only."""
        valid = EVENT_VALID_OUTCOMES[EventType.SYNC_STARTED]
        assert EventOutcome.INFO in valid
        assert len(valid) == 1

    def test_sync_completed_outcomes(self):
        """SYNC_COMPLETED can succeed or fail."""
        valid = EVENT_VALID_OUTCOMES[EventType.SYNC_COMPLETED]
        assert EventOutcome.SUCCESS in valid
        assert EventOutcome.FAILURE in valid

    def test_job_completed_outcomes(self):
        """JOB_COMPLETED is success only."""
        valid = EVENT_VALID_OUTCOMES[EventType.JOB_COMPLETED]
        assert EventOutcome.SUCCESS in valid
        assert len(valid) == 1

    def test_job_failed_outcomes(self):
        """JOB_FAILED is failure only."""
        valid = EVENT_VALID_OUTCOMES[EventType.JOB_FAILED]
        assert EventOutcome.FAILURE in valid
        assert len(valid) == 1

    def test_credentials_validation_failed_outcomes(self):
        """CREDENTIALS_VALIDATION_FAILED is failure only."""
        valid = EVENT_VALID_OUTCOMES[EventType.CREDENTIALS_VALIDATION_FAILED]
        assert EventOutcome.FAILURE in valid
        assert len(valid) == 1


class TestValidateEvent:
    """Tests for validate_event function."""

    def test_valid_activity_ingested_success(self):
        """Valid: ACTIVITY_INGESTED with SUCCESS."""
        assert validate_event(EventType.ACTIVITY_INGESTED, EventOutcome.SUCCESS) is True

    def test_valid_activity_ingested_failure(self):
        """Valid: ACTIVITY_INGESTED with FAILURE."""
        assert validate_event(EventType.ACTIVITY_INGESTED, EventOutcome.FAILURE) is True

    def test_invalid_activity_ingested_info(self):
        """Invalid: ACTIVITY_INGESTED with INFO."""
        assert validate_event(EventType.ACTIVITY_INGESTED, EventOutcome.INFO) is False

    def test_valid_activity_deleted_info(self):
        """Valid: ACTIVITY_DELETED with INFO."""
        assert validate_event(EventType.ACTIVITY_DELETED, EventOutcome.INFO) is True

    def test_invalid_activity_deleted_success(self):
        """Invalid: ACTIVITY_DELETED with SUCCESS."""
        assert validate_event(EventType.ACTIVITY_DELETED, EventOutcome.SUCCESS) is False

    def test_valid_sync_started_info(self):
        """Valid: SYNC_STARTED with INFO."""
        assert validate_event(EventType.SYNC_STARTED, EventOutcome.INFO) is True

    def test_invalid_sync_started_success(self):
        """Invalid: SYNC_STARTED with SUCCESS."""
        assert validate_event(EventType.SYNC_STARTED, EventOutcome.SUCCESS) is False

    def test_valid_job_completed_success(self):
        """Valid: JOB_COMPLETED with SUCCESS."""
        assert validate_event(EventType.JOB_COMPLETED, EventOutcome.SUCCESS) is True

    def test_invalid_job_completed_failure(self):
        """Invalid: JOB_COMPLETED with FAILURE."""
        assert validate_event(EventType.JOB_COMPLETED, EventOutcome.FAILURE) is False

    def test_valid_job_failed_failure(self):
        """Valid: JOB_FAILED with FAILURE."""
        assert validate_event(EventType.JOB_FAILED, EventOutcome.FAILURE) is True

    def test_all_event_types_have_at_least_one_valid_outcome(self):
        """Every event type should pass validation with at least one outcome."""
        for event_type in EventType:
            valid_count = sum(1 for outcome in EventOutcome if validate_event(event_type, outcome))
            assert valid_count > 0, f"{event_type} has no valid outcomes"


class TestEventDomains:
    """Tests for event domain organization."""

    def test_activity_domain_events(self):
        """Activity domain has expected events."""
        activity_events = [e for e in EventType if e.domain == "activity"]
        assert EventType.ACTIVITY_INGESTED in activity_events
        assert EventType.ACTIVITY_DELETED in activity_events

    def test_sync_domain_events(self):
        """Sync domain has expected events."""
        sync_events = [e for e in EventType if e.domain == "sync"]
        assert EventType.SYNC_STARTED in sync_events
        assert EventType.SYNC_COMPLETED in sync_events

    def test_import_domain_events(self):
        """Import domain has expected events."""
        import_events = [e for e in EventType if e.domain == "import"]
        assert EventType.IMPORT_STARTED in import_events
        assert EventType.IMPORT_COMPLETED in import_events

    def test_admin_domain_events(self):
        """Admin domain has expected events."""
        admin_events = [e for e in EventType if e.domain == "admin"]
        assert EventType.ADMIN_NUKE_ACTIVITIES in admin_events
        assert EventType.ADMIN_NUKE_INTEGRATIONS in admin_events
        assert EventType.ADMIN_NUKE_ACCOUNT in admin_events

    def test_job_domain_events(self):
        """Job domain has expected events."""
        job_events = [e for e in EventType if e.domain == "job"]
        assert EventType.JOB_COMPLETED in job_events
        assert EventType.JOB_FAILED in job_events
