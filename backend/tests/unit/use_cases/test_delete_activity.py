"""Unit tests for DeleteActivity use case using fake repos."""

from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest

from tests.fakes.activity_repo import FakeActivityRepo
from trainingdash.repositories.postgres.models import Activity
from trainingdash.use_cases import DeleteActivity


@pytest.fixture
def activity_repo():
    return FakeActivityRepo()


@pytest.fixture
def mock_db_session():
    """Create a mock database session for event logging."""
    return mock.AsyncMock()


@pytest.fixture
def use_case(activity_repo, mock_db_session):
    with mock.patch("trainingdash.use_cases.delete_activity.PostgresEventRepo") as mock_event_repo_cls:
        mock_event_repo_cls.return_value.log = mock.AsyncMock()
        use_case = DeleteActivity(activity_repo, mock_db_session)
        yield use_case


@pytest.fixture
def sample_activity():
    """Create a sample activity for testing."""
    return Activity(
        id=uuid4(),
        user_id=1,
        source="upload",
        source_ref="test.fit",
        started_at=datetime(2024, 3, 15, 10, 0, 0),
        total_distance_m=10000,
        moving_time_s=3600,
        elapsed_time_s=3600,
    )


class TestDeleteActivityUseCase:
    @pytest.mark.asyncio
    async def test_delete_existing_activity_returns_true(self, use_case, activity_repo, sample_activity):
        """Deleting an existing activity owned by the user returns True."""
        await activity_repo.save(sample_activity)

        with mock.patch("trainingdash.jobs.enqueue_recalculate_after_delete_job"):
            result = await use_case.execute(
                user_id=sample_activity.user_id,
                activity_id=sample_activity.id,
            )

        assert result is True
        assert await activity_repo.get_by_id(sample_activity.id, sample_activity.user_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_activity_returns_false(self, use_case):
        """Deleting a non-existent activity returns False."""
        result = await use_case.execute(
            user_id=1,
            activity_id=uuid4(),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_other_users_activity_returns_false(self, use_case, activity_repo, sample_activity):
        """Cannot delete another user's activity."""
        await activity_repo.save(sample_activity)

        result = await use_case.execute(
            user_id=999,  # Different user
            activity_id=sample_activity.id,
        )

        assert result is False
        # Activity still exists
        assert await activity_repo.get_by_id(sample_activity.id, sample_activity.user_id) is not None

    @pytest.mark.asyncio
    async def test_delete_enqueues_recalculation_job(self, use_case, activity_repo, sample_activity):
        """Successful delete enqueues a fitness recalculation job."""
        await activity_repo.save(sample_activity)

        with mock.patch("trainingdash.jobs.enqueue_recalculate_after_delete_job") as mock_enqueue:
            result = await use_case.execute(
                user_id=sample_activity.user_id,
                activity_id=sample_activity.id,
            )

        assert result is True
        mock_enqueue.assert_called_once_with(sample_activity.user_id)

    @pytest.mark.asyncio
    async def test_delete_succeeds_even_if_enqueue_fails(self, use_case, activity_repo, sample_activity):
        """Delete succeeds even if recalculation job enqueue fails."""
        await activity_repo.save(sample_activity)

        with mock.patch(
            "trainingdash.jobs.enqueue_recalculate_after_delete_job",
            side_effect=Exception("Redis unavailable"),
        ):
            result = await use_case.execute(
                user_id=sample_activity.user_id,
                activity_id=sample_activity.id,
            )

        # Delete still succeeds
        assert result is True
        assert await activity_repo.get_by_id(sample_activity.id, sample_activity.user_id) is None

    @pytest.mark.asyncio
    async def test_delete_does_not_enqueue_on_not_found(self, use_case):
        """No recalculation job is enqueued when activity not found."""
        with mock.patch("trainingdash.jobs.enqueue_recalculate_after_delete_job") as mock_enqueue:
            result = await use_case.execute(
                user_id=1,
                activity_id=uuid4(),
            )

        assert result is False
        mock_enqueue.assert_not_called()
