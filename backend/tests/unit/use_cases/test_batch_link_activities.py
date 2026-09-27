"""Unit tests for BatchLinkActivities use case using fake repos."""

from datetime import date, datetime
from uuid import uuid4

import pytest

from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.ride_event_repo import (
    FakeJournalEntryActivityRepo,
    FakeJournalEntryRepo,
    FakeRideEventRepo,
)
from trainingdash.repositories.postgres.models import Activity, RideEvent
from trainingdash.use_cases.batch_link_activities import (
    BatchLinkActivities,
    BatchLinkResult,
    LinkedActivity,
)


@pytest.fixture
def event_repo():
    return FakeRideEventRepo()


@pytest.fixture
def entry_repo():
    return FakeJournalEntryRepo()


@pytest.fixture
def activity_repo():
    return FakeActivityRepo()


@pytest.fixture
def activity_link_repo():
    return FakeJournalEntryActivityRepo()


@pytest.fixture
def use_case(event_repo, entry_repo, activity_repo, activity_link_repo):
    return BatchLinkActivities(
        event_repo=event_repo,
        entry_repo=entry_repo,
        activity_repo=activity_repo,
        activity_link_repo=activity_link_repo,
    )


@pytest.fixture
def sample_event():
    """Create a sample ride event for testing."""
    return RideEvent(
        id=uuid4(),
        user_id=1,
        title="Test Event",
        event_type="training_camp",
        start_date=date(2024, 6, 1),
        end_date=date(2024, 6, 7),
    )


@pytest.fixture
def sample_activities():
    """Create sample activities for testing."""
    return [
        Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref=f"test{i}.fit",
            started_at=datetime(2024, 6, i + 1, 10, 0, 0),
            total_distance_m=50000,
            moving_time_s=7200,
            elapsed_time_s=7200,
        )
        for i in range(3)
    ]


class TestBatchLinkActivities:
    """Tests for BatchLinkActivities use case."""

    @pytest.mark.asyncio
    async def test_links_activities_to_event(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
        sample_activities,
    ):
        """Should link multiple activities to an event."""
        # Setup: Save event and activities
        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})

        for activity in sample_activities:
            await activity_repo.save(activity)

        activity_ids = [a.id for a in sample_activities]

        # Execute
        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=activity_ids,
        )

        # Verify
        assert isinstance(result, BatchLinkResult)
        assert len(result.linked) == 3
        assert result.skipped_count == 0

        for linked in result.linked:
            assert isinstance(linked, LinkedActivity)
            assert linked.activity_id in activity_ids

    @pytest.mark.asyncio
    async def test_creates_journal_entries_per_date(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
        sample_activities,
    ):
        """Should create separate journal entries for different dates."""
        # Setup
        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})

        for activity in sample_activities:
            await activity_repo.save(activity)

        activity_ids = [a.id for a in sample_activities]

        # Execute
        await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=activity_ids,
        )

        # Verify: Should have 3 entries (one per day)
        entries = await entry_repo.list_for_event(sample_event.id)
        assert len(entries) == 3

    @pytest.mark.asyncio
    async def test_reuses_existing_journal_entry_for_same_date(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
    ):
        """Should reuse journal entry if activity falls on same date."""
        # Setup: Two activities on same date
        activity1 = Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="test1.fit",
            started_at=datetime(2024, 6, 1, 8, 0, 0),  # Morning ride
            total_distance_m=30000,
        )
        activity2 = Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="test2.fit",
            started_at=datetime(2024, 6, 1, 14, 0, 0),  # Afternoon ride
            total_distance_m=40000,
        )

        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})
        await activity_repo.save(activity1)
        await activity_repo.save(activity2)

        # Execute
        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=[activity1.id, activity2.id],
        )

        # Verify: Both linked to same entry
        assert len(result.linked) == 2
        entry_ids = {linked.journal_entry_id for linked in result.linked}
        assert len(entry_ids) == 1  # Same journal entry

    @pytest.mark.asyncio
    async def test_skips_activities_not_owned_by_user(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
    ):
        """Should skip activities that don't belong to the user."""
        # Setup: Activity owned by different user
        other_user_activity = Activity(
            id=uuid4(),
            user_id=999,  # Different user
            source="upload",
            source_ref="other.fit",
            started_at=datetime(2024, 6, 1, 10, 0, 0),
            total_distance_m=50000,
        )

        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})
        await activity_repo.save(other_user_activity)

        # Execute
        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=[other_user_activity.id],
        )

        # Verify
        assert len(result.linked) == 0
        assert result.skipped_count == 1

    @pytest.mark.asyncio
    async def test_skips_nonexistent_activities(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
    ):
        """Should skip activities that don't exist."""
        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})

        # Execute with non-existent activity IDs
        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=[uuid4(), uuid4()],
        )

        # Verify
        assert len(result.linked) == 0
        assert result.skipped_count == 2

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_event(
        self,
        use_case,
        activity_repo,
        sample_activities,
    ):
        """Should raise ValueError when event doesn't exist."""
        for activity in sample_activities:
            await activity_repo.save(activity)

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                user_id=1,
                event_id=uuid4(),  # Non-existent event
                activity_ids=[a.id for a in sample_activities],
            )

    @pytest.mark.asyncio
    async def test_raises_for_event_owned_by_different_user(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
        sample_activities,
    ):
        """Should raise ValueError when event belongs to different user."""
        await event_repo.save(sample_event)
        for activity in sample_activities:
            await activity_repo.save(activity)

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(
                user_id=999,  # Different user
                event_id=sample_event.id,
                activity_ids=[a.id for a in sample_activities],
            )

    @pytest.mark.asyncio
    async def test_empty_activity_list(
        self,
        use_case,
        event_repo,
        entry_repo,
        sample_event,
    ):
        """Should handle empty activity list gracefully."""
        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})

        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=[],
        )

        assert len(result.linked) == 0
        assert result.skipped_count == 0

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_activities(
        self,
        use_case,
        event_repo,
        entry_repo,
        activity_repo,
        sample_event,
    ):
        """Should link valid activities and skip invalid ones."""
        # Setup: One valid, one from different user, one non-existent
        valid_activity = Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="valid.fit",
            started_at=datetime(2024, 6, 1, 10, 0, 0),
            total_distance_m=50000,
        )
        other_user_activity = Activity(
            id=uuid4(),
            user_id=999,
            source="upload",
            source_ref="other.fit",
            started_at=datetime(2024, 6, 2, 10, 0, 0),
            total_distance_m=50000,
        )

        await event_repo.save(sample_event)
        entry_repo.set_event_owners({sample_event.id: sample_event.user_id})
        await activity_repo.save(valid_activity)
        await activity_repo.save(other_user_activity)

        # Execute
        result = await use_case.execute(
            user_id=sample_event.user_id,
            event_id=sample_event.id,
            activity_ids=[valid_activity.id, other_user_activity.id, uuid4()],
        )

        # Verify
        assert len(result.linked) == 1
        assert result.linked[0].activity_id == valid_activity.id
        assert result.skipped_count == 2


class TestLinkedActivityDataclass:
    """Tests for LinkedActivity dataclass."""

    def test_linked_activity_creation(self):
        """LinkedActivity should store all fields correctly."""
        entry_id = uuid4()
        activity_id = uuid4()

        linked = LinkedActivity(
            link_id=1,
            journal_entry_id=entry_id,
            activity_id=activity_id,
            sort_order=0,
        )

        assert linked.link_id == 1
        assert linked.journal_entry_id == entry_id
        assert linked.activity_id == activity_id
        assert linked.sort_order == 0


class TestBatchLinkResultDataclass:
    """Tests for BatchLinkResult dataclass."""

    def test_batch_link_result_creation(self):
        """BatchLinkResult should store linked list and skipped count."""
        result = BatchLinkResult(
            linked=[],
            skipped_count=5,
        )

        assert result.linked == []
        assert result.skipped_count == 5
