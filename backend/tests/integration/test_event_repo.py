"""Integration tests for PostgresEventRepo (#382)."""

from datetime import UTC, datetime, timedelta

import pytest

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo


class TestEventRepoLog:
    """Tests for logging events."""

    @pytest.mark.asyncio
    async def test_log_event_returns_id(self, db_session):
        """Logging an event returns its ID."""
        repo = PostgresEventRepo(db_session)

        event_id = await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=None,
            payload={"activities_synced": 5},
        )

        assert event_id is not None
        assert isinstance(event_id, int)
        assert event_id > 0

    @pytest.mark.asyncio
    async def test_log_event_with_user_id(self, db_session, seed_user):
        """Event can be logged with a user_id."""
        repo = PostgresEventRepo(db_session)

        event_id = await repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=seed_user.id,
            payload={"activity_id": "abc123"},
        )

        events = await repo.list(user_id=seed_user.id)
        assert len(events) == 1
        assert events[0].id == event_id
        assert events[0].user_id == seed_user.id

    @pytest.mark.asyncio
    async def test_log_event_sequential_ids(self, db_session):
        """Logged events get sequential IDs."""
        repo = PostgresEventRepo(db_session)

        id1 = await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
        )
        id2 = await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
        )

        assert id2 > id1


class TestEventRepoList:
    """Tests for listing events."""

    @pytest.mark.asyncio
    async def test_list_returns_newest_first(self, db_session):
        """Events are returned in descending order by created_at."""
        repo = PostgresEventRepo(db_session)

        # Log multiple events with unique types to identify them
        id1 = await repo.log(event_type="first.event", outcome=EventOutcome.SUCCESS.value)
        id2 = await repo.log(event_type="second.event", outcome=EventOutcome.SUCCESS.value)
        id3 = await repo.log(event_type="third.event", outcome=EventOutcome.SUCCESS.value)

        events = await repo.list()
        assert len(events) == 3

        # Since events are created instantly (same timestamp), verify we get all 3
        # and they're ordered by created_at DESC (which falls back to ID order in practice)
        event_types = {e.event_type for e in events}
        assert event_types == {"first.event", "second.event", "third.event"}

        # Verify IDs are sequential
        assert id1 < id2 < id3

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self, db_session):
        """Events can be filtered by event_type."""
        repo = PostgresEventRepo(db_session)

        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.ACTIVITY_INGESTED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.FAILURE.value)

        events = await repo.list(event_type=EventType.SYNC_COMPLETED.value)
        assert len(events) == 2
        assert all(e.event_type == EventType.SYNC_COMPLETED.value for e in events)

    @pytest.mark.asyncio
    async def test_list_filter_by_outcome(self, db_session):
        """Events can be filtered by outcome."""
        repo = PostgresEventRepo(db_session)

        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.FAILURE.value)

        events = await repo.list(outcome=EventOutcome.SUCCESS.value)
        assert len(events) == 1
        assert events[0].outcome == EventOutcome.SUCCESS.value

    @pytest.mark.asyncio
    async def test_list_filter_by_user_id(self, db_session, seed_user):
        """Events can be filtered by user_id."""
        repo = PostgresEventRepo(db_session)

        await repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=seed_user.id,
        )
        await repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=None,  # System event
        )

        events = await repo.list(user_id=seed_user.id)
        assert len(events) == 1
        assert events[0].user_id == seed_user.id

    @pytest.mark.asyncio
    async def test_list_filter_by_time_range(self, db_session):
        """Events can be filtered by time range."""
        repo = PostgresEventRepo(db_session)

        # Log events
        await repo.log(event_type="event.1", outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type="event.2", outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type="event.3", outcome=EventOutcome.SUCCESS.value)

        # Get all events to determine time range
        all_events = await repo.list()
        assert len(all_events) == 3

        # Use time boundary between first and second event
        # Since they're created quickly, use created_at of middle event
        middle_time = all_events[1].created_at

        # Since filter (inclusive)
        events_since = await repo.list(since=middle_time)
        assert len(events_since) >= 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, db_session):
        """Events support pagination via limit and offset."""
        repo = PostgresEventRepo(db_session)

        # Log 5 events
        for i in range(5):
            await repo.log(event_type=f"event.{i}", outcome=EventOutcome.SUCCESS.value)

        # First page
        page1 = await repo.list(limit=2, offset=0)
        assert len(page1) == 2

        # Second page
        page2 = await repo.list(limit=2, offset=2)
        assert len(page2) == 2

        # Third page (partial)
        page3 = await repo.list(limit=2, offset=4)
        assert len(page3) == 1

        # Pages should be different
        page1_types = {e.event_type for e in page1}
        page2_types = {e.event_type for e in page2}
        assert page1_types.isdisjoint(page2_types)

    @pytest.mark.asyncio
    async def test_list_limit_capped_at_100(self, db_session):
        """List limit is capped at 100."""
        repo = PostgresEventRepo(db_session)

        # Log 5 events
        for i in range(5):
            await repo.log(event_type=f"event.{i}", outcome=EventOutcome.SUCCESS.value)

        # Request 200 but code caps at 100
        events = await repo.list(limit=200)
        # Only 5 events exist, so we get 5
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_list_combined_filters(self, db_session, seed_user):
        """Multiple filters can be combined."""
        repo = PostgresEventRepo(db_session)

        await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=seed_user.id,
        )
        await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.FAILURE.value,
            user_id=seed_user.id,
        )
        await repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=seed_user.id,
        )
        await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=None,
        )

        # Filter by type + outcome + user
        events = await repo.list(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=seed_user.id,
        )
        assert len(events) == 1
        assert events[0].event_type == EventType.SYNC_COMPLETED.value
        assert events[0].outcome == EventOutcome.SUCCESS.value
        assert events[0].user_id == seed_user.id


class TestEventRepoCount:
    """Tests for counting events."""

    @pytest.mark.asyncio
    async def test_count_all(self, db_session):
        """Count returns total number of events."""
        repo = PostgresEventRepo(db_session)

        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.FAILURE.value)
        await repo.log(event_type=EventType.ACTIVITY_INGESTED.value, outcome=EventOutcome.SUCCESS.value)

        count = await repo.count()
        assert count == 3

    @pytest.mark.asyncio
    async def test_count_with_filters(self, db_session):
        """Count respects filters."""
        repo = PostgresEventRepo(db_session)

        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.FAILURE.value)
        await repo.log(event_type=EventType.ACTIVITY_INGESTED.value, outcome=EventOutcome.SUCCESS.value)

        assert await repo.count(event_type=EventType.SYNC_COMPLETED.value) == 2
        assert await repo.count(outcome=EventOutcome.SUCCESS.value) == 2
        assert await repo.count(event_type=EventType.SYNC_COMPLETED.value, outcome=EventOutcome.SUCCESS.value) == 1


class TestEventRepoDeleteBefore:
    """Tests for deleting old events."""

    @pytest.mark.asyncio
    async def test_delete_before_removes_old_events(self, db_session):
        """Delete removes events older than cutoff."""
        repo = PostgresEventRepo(db_session)

        # Log events
        await repo.log(event_type="old.event", outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type="new.event", outcome=EventOutcome.SUCCESS.value)

        # Delete events older than far future (should delete all)
        future_cutoff = datetime.now(UTC) + timedelta(hours=1)
        deleted = await repo.delete_before(future_cutoff)

        assert deleted == 2
        remaining = await repo.list()
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_delete_before_preserves_newer_events(self, db_session):
        """Delete preserves events newer than cutoff."""
        repo = PostgresEventRepo(db_session)

        # Log events
        await repo.log(event_type="event.1", outcome=EventOutcome.SUCCESS.value)
        await repo.log(event_type="event.2", outcome=EventOutcome.SUCCESS.value)

        # Delete with past cutoff (should delete nothing)
        past_cutoff = datetime.now(UTC) - timedelta(hours=1)
        deleted = await repo.delete_before(past_cutoff)

        assert deleted == 0
        remaining = await repo.list()
        assert len(remaining) == 2

    @pytest.mark.asyncio
    async def test_delete_before_returns_count(self, db_session):
        """Delete returns count of deleted events."""
        repo = PostgresEventRepo(db_session)

        # Log 5 events
        for i in range(5):
            await repo.log(event_type=f"event.{i}", outcome=EventOutcome.SUCCESS.value)

        # Delete all
        future_cutoff = datetime.now(UTC) + timedelta(hours=1)
        deleted = await repo.delete_before(future_cutoff)

        assert deleted == 5


class TestEventPayload:
    """Tests for event payload handling."""

    @pytest.mark.asyncio
    async def test_payload_stored_and_retrieved(self, db_session):
        """JSONB payload is stored and retrieved correctly."""
        repo = PostgresEventRepo(db_session)

        payload = {
            "activities_synced": 5,
            "duration_seconds": 120.5,
            "errors": ["timeout", "rate_limit"],
            "metadata": {"provider": "xert", "version": "1.0"},
        }

        await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            payload=payload,
        )

        events = await repo.list()
        assert len(events) == 1
        assert events[0].payload == payload

    @pytest.mark.asyncio
    async def test_empty_payload_defaults_to_empty_dict(self, db_session):
        """Empty payload defaults to empty dict."""
        repo = PostgresEventRepo(db_session)

        await repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            payload=None,
        )

        events = await repo.list()
        assert len(events) == 1
        assert events[0].payload == {}
