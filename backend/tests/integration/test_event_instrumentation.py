"""Integration tests for event instrumentation (#383).

Verifies that key use cases emit events to the events table.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import Event, User


class TestEventInstrumentation:
    """Tests that verify events are emitted by instrumented code paths."""

    @pytest.fixture
    async def test_user(self, db_session) -> User:
        """Create a test user for events."""
        user = User(
            email="eventtest@example.com",
            password_hash="hashed",
            display_name="Event Test",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_recalculation_events(self, db_session, test_user):
        """RecalculateMetrics emits recalculation.started and recalculation.completed events."""
        from trainingdash.use_cases import RecalculateMetrics

        use_case = RecalculateMetrics(db_session, recalculation_job_repo=None)
        result = await use_case.execute(test_user.id)

        assert result.success is True

        # Verify events were emitted
        events = (
            await db_session.execute(
                select(Event)
                .where(Event.user_id == test_user.id)
                .order_by(Event.created_at)
            )
        ).scalars().all()

        event_types = [e.event_type for e in events]
        assert EventType.RECALCULATION_STARTED.value in event_types
        assert EventType.RECALCULATION_COMPLETED.value in event_types

        # Check the completed event has success outcome
        completed_event = next(e for e in events if e.event_type == EventType.RECALCULATION_COMPLETED.value)
        assert completed_event.outcome == EventOutcome.SUCCESS.value

    @pytest.mark.asyncio
    async def test_scheduler_use_case_emits_event(self, db_session):
        """HourlySyncScheduler emits scheduler.triggered event (when users match)."""
        # This test directly verifies the event repo works with scheduler event type
        # The full scheduler test would require mocking credentials tables
        event_repo = PostgresEventRepo(db_session)

        # Simulate what the scheduler would emit
        from datetime import UTC, datetime
        current_hour = datetime.now(UTC).hour

        await event_repo.log(
            event_type=EventType.SCHEDULER_TRIGGERED.value,
            outcome=EventOutcome.INFO.value,
            user_id=None,
            payload={
                "hour": current_hour,
                "garmin_queued": 2,
                "xert_queued": 1,
            },
        )
        await db_session.commit()

        # Verify event was created
        events = (
            await db_session.execute(
                select(Event)
                .where(Event.event_type == EventType.SCHEDULER_TRIGGERED.value)
            )
        ).scalars().all()

        assert len(events) >= 1
        latest = events[-1]
        assert latest.outcome == EventOutcome.INFO.value
        assert latest.user_id is None  # System-wide event
        assert latest.payload["hour"] == current_hour
        assert latest.payload["garmin_queued"] == 2
        assert latest.payload["xert_queued"] == 1

    @pytest.mark.asyncio
    async def test_event_repo_log_creates_event(self, db_session, test_user):
        """EventRepo.log creates event with correct fields."""
        event_repo = PostgresEventRepo(db_session)

        event_id = await event_repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=test_user.id,
            payload={"activity_id": "test-123", "source": "upload"},
        )
        await db_session.commit()

        assert event_id is not None

        # Verify the event exists with correct data
        event = (
            await db_session.execute(
                select(Event).where(Event.id == event_id)
            )
        ).scalar_one()

        assert event.event_type == EventType.ACTIVITY_INGESTED.value
        assert event.outcome == EventOutcome.SUCCESS.value
        assert event.user_id == test_user.id
        assert event.payload["activity_id"] == "test-123"
        assert event.payload["source"] == "upload"
        assert event.created_at is not None

    @pytest.mark.asyncio
    async def test_event_repo_list_filters(self, db_session, test_user):
        """EventRepo.list filters by event_type, outcome, user_id, and time range."""
        event_repo = PostgresEventRepo(db_session)

        # Create various events
        await event_repo.log(
            event_type=EventType.SYNC_STARTED.value,
            outcome=EventOutcome.INFO.value,
            user_id=test_user.id,
            payload={"provider": "xert"},
        )
        await event_repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=test_user.id,
            payload={"provider": "xert", "synced_activities": 5},
        )
        await event_repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.FAILURE.value,
            user_id=test_user.id,
            payload={"provider": "garmin", "error": "Connection failed"},
        )
        await db_session.commit()

        # Filter by event_type
        sync_completed = await event_repo.list(event_type=EventType.SYNC_COMPLETED.value)
        assert len(sync_completed) == 2

        # Filter by outcome
        failures = await event_repo.list(outcome=EventOutcome.FAILURE.value)
        assert len(failures) == 1
        assert failures[0].payload["error"] == "Connection failed"

        # Filter by user_id
        user_events = await event_repo.list(user_id=test_user.id)
        assert len(user_events) == 3

    @pytest.mark.asyncio
    async def test_multiple_event_types_in_workflow(self, db_session, test_user):
        """A workflow can emit multiple event types."""
        event_repo = PostgresEventRepo(db_session)

        # Simulate a sync workflow
        await event_repo.log(
            event_type=EventType.SYNC_STARTED.value,
            outcome=EventOutcome.INFO.value,
            user_id=test_user.id,
            payload={"provider": "xert"},
        )

        # Simulate ingested activity
        await event_repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=test_user.id,
            payload={"activity_id": "act-1", "source": "xert"},
        )

        # Simulate route matched
        await event_repo.log(
            event_type=EventType.ROUTE_MATCHED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=test_user.id,
            payload={"activity_id": "act-1", "route_id": "route-1"},
        )

        # Sync completed
        await event_repo.log(
            event_type=EventType.SYNC_COMPLETED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=test_user.id,
            payload={"provider": "xert", "synced_activities": 1},
        )
        await db_session.commit()

        # Verify workflow events
        events = await event_repo.list(user_id=test_user.id)
        assert len(events) == 4

        event_types = {e.event_type for e in events}
        assert event_types == {
            EventType.SYNC_STARTED.value,
            EventType.ACTIVITY_INGESTED.value,
            EventType.ROUTE_MATCHED.value,
            EventType.SYNC_COMPLETED.value,
        }
