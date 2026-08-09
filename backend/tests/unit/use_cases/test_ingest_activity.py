"""Unit tests for IngestActivity use case."""

from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity
from trainingdash.use_cases import IngestActivity


class MockAsyncSession:
    """Minimal mock for AsyncSession."""

    pass


@pytest.fixture
def db_session():
    return MockAsyncSession()


@pytest.fixture
def use_case(db_session):
    return IngestActivity(db_session)


@pytest.fixture
def sample_parsed_fit():
    """Sample parsed FIT data."""
    return {
        "started_at": datetime(2024, 3, 15, 10, 0, 0),
        "total_distance_m": 10000.0,
        "moving_time_s": 3600,
        "elapsed_time_s": 3700,
        "records": [{"timestamp": datetime(2024, 3, 15, 10, 0, i), "power_w": 200} for i in range(10)],
        "laps": [],
        "summary": {},
    }


@pytest.fixture
def sample_activity():
    """Sample activity returned after storage."""
    return Activity(
        id=uuid4(),
        user_id=1,
        source="upload",
        source_ref="test.fit",
        started_at=datetime(2024, 3, 15, 10, 0, 0),
        total_distance_m=10000,
        moving_time_s=3600,
        elapsed_time_s=3700,
    )


class TestIngestActivityUseCase:
    @pytest.mark.asyncio
    async def test_execute_success_returns_activity(self, use_case, sample_parsed_fit, sample_activity):
        """Successful ingest returns the created activity."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=sample_activity):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    result = await use_case.execute(
                        user_id=1,
                        fit_data=b"fake fit data",
                        source="upload",
                        source_ref="test.fit",
                    )

        assert result is not None
        assert result.id == sample_activity.id
        mock_pipeline.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_parse_failure_returns_none(self, use_case):
        """Failed FIT parsing returns None."""
        with mock.patch("trainingdash.ingest.parse_records", side_effect=Exception("Invalid FIT")):
            result = await use_case.execute(
                user_id=1,
                fit_data=b"invalid data",
                source="upload",
                source_ref="bad.fit",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_skips_duplicates_for_provider_sync(self, use_case, sample_parsed_fit):
        """Duplicate detection skips activity for provider syncs."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest.is_duplicate_activity", return_value=True):
                result = await use_case.execute(
                    user_id=1,
                    fit_data=b"fake fit data",
                    source="xert",  # Provider sync, not upload
                    source_ref="xert:123",
                )

        assert result is None

    @pytest.mark.asyncio
    async def test_execute_skips_duplicate_check_for_uploads(self, use_case, sample_parsed_fit, sample_activity):
        """Upload source skips duplicate detection."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest.is_duplicate_activity") as mock_dup:
                with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=sample_activity):
                    with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                        mock_pipeline = mock.AsyncMock()
                        MockPipeline.return_value = mock_pipeline

                        result = await use_case.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        # Duplicate check should not be called for uploads
        mock_dup.assert_not_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_passes_batch_mode_to_pipeline(self, use_case, sample_parsed_fit, sample_activity):
        """batch_mode flag is passed to ActivityPipeline."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=sample_activity):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    await use_case.execute(
                        user_id=1,
                        fit_data=b"fake fit data",
                        source="upload",
                        source_ref="test.fit",
                        batch_mode=True,
                    )

        # Verify batch_mode was passed
        call_kwargs = MockPipeline.call_args.kwargs
        assert call_kwargs["batch_mode"] is True
