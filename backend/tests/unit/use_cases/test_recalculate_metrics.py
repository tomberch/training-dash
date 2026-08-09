"""Unit tests for RecalculateMetrics use case using fake repos."""

from unittest import mock

import pytest

from tests.fakes.recalculation_job_repo import FakeRecalculationJobRepo
from trainingdash.use_cases import RecalculateMetrics


class MockAsyncSession:
    """Minimal mock for AsyncSession to satisfy the use case."""

    async def commit(self):
        pass


@pytest.fixture
def db_session():
    return MockAsyncSession()


@pytest.fixture
def job_repo():
    return FakeRecalculationJobRepo()


@pytest.fixture
def use_case(db_session, job_repo):
    return RecalculateMetrics(db_session, job_repo)


class TestRecalculateMetricsUseCase:
    @pytest.mark.asyncio
    async def test_execute_success_updates_job_status(self, use_case, job_repo):
        """Successful execution updates job status to completed."""
        user_id = 1

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            return_value=5,
        ):
            result = await use_case.execute(user_id)

        assert result.success is True
        assert result.user_id == user_id
        assert result.activities_updated == 5
        assert result.error is None

        # Check job status
        job = await job_repo.get_by_user_id(user_id)
        assert job is not None
        assert job.status == "completed"
        assert job.activities_updated == 5
        assert job.error_message is None

    @pytest.mark.asyncio
    async def test_execute_marks_running_before_processing(self, db_session, job_repo):
        """Job is marked as running before metrics are computed."""
        user_id = 1
        running_status = []

        async def capture_status(*args, **kwargs):
            # Capture the job status at the time backfill is called
            job = await job_repo.get_by_user_id(user_id)
            running_status.append(job.status if job else None)
            return 3

        use_case = RecalculateMetrics(db_session, job_repo)

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            side_effect=capture_status,
        ):
            await use_case.execute(user_id)

        assert running_status == ["running"]

    @pytest.mark.asyncio
    async def test_execute_failure_marks_job_failed(self, use_case, job_repo):
        """Failed execution marks job status as failed."""
        user_id = 1

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            side_effect=Exception("Database error"),
        ):
            result = await use_case.execute(user_id)

        assert result.success is False
        assert result.user_id == user_id
        assert result.activities_updated == 0
        assert "Database error" in result.error

        # Check job status
        job = await job_repo.get_by_user_id(user_id)
        assert job is not None
        assert job.status == "failed"
        assert "Database error" in job.error_message

    @pytest.mark.asyncio
    async def test_execute_without_job_repo_still_works(self, db_session):
        """Use case works without a job repo (no status tracking)."""
        use_case = RecalculateMetrics(db_session, recalculation_job_repo=None)
        user_id = 1

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            return_value=7,
        ):
            result = await use_case.execute(user_id)

        assert result.success is True
        assert result.activities_updated == 7

    @pytest.mark.asyncio
    async def test_execute_zero_activities_still_succeeds(self, use_case, job_repo):
        """Zero activities updated is still a successful result."""
        user_id = 1

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            return_value=0,
        ):
            result = await use_case.execute(user_id)

        assert result.success is True
        assert result.activities_updated == 0

        job = await job_repo.get_by_user_id(user_id)
        assert job.status == "completed"
        assert job.activities_updated == 0

    @pytest.mark.asyncio
    async def test_error_message_truncated(self, use_case, job_repo):
        """Long error messages are truncated to 500 characters."""
        user_id = 1
        long_error = "x" * 1000

        with mock.patch(
            "trainingdash.ingest.backfill_activity_metrics",
            side_effect=Exception(long_error),
        ):
            result = await use_case.execute(user_id)

        assert len(result.error) == 500

        job = await job_repo.get_by_user_id(user_id)
        assert len(job.error_message) == 500
