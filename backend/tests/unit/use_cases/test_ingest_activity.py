"""Unit tests for IngestActivity use case."""

from datetime import datetime
from unittest import mock
from uuid import uuid4

import pytest

from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
from trainingdash.repositories.postgres.models import Activity
from trainingdash.use_cases import IngestActivity


class MockAsyncSession:
    """Minimal mock for AsyncSession."""

    def add(self, obj):
        """Mock add method for event logging."""
        pass

    async def flush(self):
        """Mock flush method for event logging."""
        pass


@pytest.fixture
def db_session():
    return MockAsyncSession()


@pytest.fixture
def pacing_repo():
    return FakePacingCoefficientsRepo()


@pytest.fixture
def use_case(db_session):
    return IngestActivity(db_session)


@pytest.fixture
def use_case_with_pacing(db_session, pacing_repo):
    return IngestActivity(db_session, pacing_repo)


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


class TestIngestActivityCalibration:
    """Tests for automatic pacing calibration after ingestion."""

    @pytest.fixture
    def activity_with_power(self):
        """Activity with measured power and sufficient elevation."""
        return Activity(
            id=uuid4(),
            user_id=1,
            bike_id=42,
            source="upload",
            source_ref="test.fit",
            started_at=datetime(2024, 3, 15, 10, 0, 0),
            total_distance_m=50000,
            moving_time_s=7200,
            elapsed_time_s=7500,
            avg_power_w=200,
            power_source="measured",
            elevation_gain_m=500,
        )

    @pytest.fixture
    def activity_no_power(self):
        """Activity without power data."""
        return Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="test.fit",
            started_at=datetime(2024, 3, 15, 10, 0, 0),
            total_distance_m=50000,
            moving_time_s=7200,
            elapsed_time_s=7500,
            avg_power_w=None,
            power_source=None,
            elevation_gain_m=500,
        )

    @pytest.fixture
    def activity_estimated_power(self):
        """Activity with estimated (not measured) power."""
        return Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="test.fit",
            started_at=datetime(2024, 3, 15, 10, 0, 0),
            total_distance_m=50000,
            moving_time_s=7200,
            elapsed_time_s=7500,
            avg_power_w=180,
            power_source="estimated",
            elevation_gain_m=500,
        )

    @pytest.fixture
    def activity_low_elevation(self):
        """Activity with measured power but insufficient elevation."""
        return Activity(
            id=uuid4(),
            user_id=1,
            source="upload",
            source_ref="test.fit",
            started_at=datetime(2024, 3, 15, 10, 0, 0),
            total_distance_m=50000,
            moving_time_s=7200,
            elapsed_time_s=7500,
            avg_power_w=200,
            power_source="measured",
            elevation_gain_m=50,  # Less than 100m threshold
        )

    @pytest.mark.asyncio
    async def test_calibration_triggered_for_activity_with_power(
        self, use_case_with_pacing, sample_parsed_fit, activity_with_power
    ):
        """Calibration is triggered for activities with measured power."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_with_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        mock_calibrate = mock.AsyncMock()
                        mock_calibrate.execute = mock.AsyncMock(return_value=mock.MagicMock(coefficients_updated=True))
                        MockCalibrate.return_value = mock_calibrate

                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                            batch_mode=False,
                        )

        assert result is not None
        # Should be called twice: once for bike_id=42, once for user default (bike_id=None)
        assert mock_calibrate.execute.call_count == 2
        mock_calibrate.execute.assert_any_call(1, bike_id=42)
        mock_calibrate.execute.assert_any_call(1, bike_id=None)

    @pytest.mark.asyncio
    async def test_calibration_skipped_in_batch_mode(
        self, use_case_with_pacing, sample_parsed_fit, activity_with_power
    ):
        """Calibration is skipped in batch mode (handled by finalize_batch_import)."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_with_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        mock_calibrate = mock.AsyncMock()
                        MockCalibrate.return_value = mock_calibrate

                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                            batch_mode=True,  # Batch mode
                        )

        assert result is not None
        # CalibratePacing should not be instantiated in batch mode
        MockCalibrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_calibration_skipped_when_no_pacing_repo(self, use_case, sample_parsed_fit, activity_with_power):
        """Calibration is skipped when pacing_repo is None."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_with_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        result = await use_case.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        assert result is not None
        # CalibratePacing should not be instantiated when no pacing_repo
        MockCalibrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_calibration_skipped_for_activity_without_power(
        self, use_case_with_pacing, sample_parsed_fit, activity_no_power
    ):
        """Calibration is skipped for activities without power data."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_no_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        assert result is not None
        MockCalibrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_calibration_skipped_for_estimated_power(
        self, use_case_with_pacing, sample_parsed_fit, activity_estimated_power
    ):
        """Calibration is skipped for activities with estimated (not measured) power."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_estimated_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        assert result is not None
        MockCalibrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_calibration_skipped_for_low_elevation(
        self, use_case_with_pacing, sample_parsed_fit, activity_low_elevation
    ):
        """Calibration is skipped for activities with insufficient elevation gain."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_low_elevation):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        assert result is not None
        MockCalibrate.assert_not_called()

    @pytest.mark.asyncio
    async def test_calibration_failure_does_not_fail_ingestion(
        self, use_case_with_pacing, sample_parsed_fit, activity_with_power
    ):
        """Calibration failure should not cause the ingestion to fail."""
        with mock.patch("trainingdash.ingest.parse_records", return_value=sample_parsed_fit):
            with mock.patch("trainingdash.ingest._store_parsed_fit", return_value=activity_with_power):
                with mock.patch("trainingdash.activity_pipeline.ActivityPipeline") as MockPipeline:
                    mock_pipeline = mock.AsyncMock()
                    MockPipeline.return_value = mock_pipeline

                    with mock.patch("trainingdash.use_cases.calibrate_pacing.CalibratePacing") as MockCalibrate:
                        mock_calibrate = mock.AsyncMock()
                        mock_calibrate.execute = mock.AsyncMock(side_effect=Exception("Calibration database error"))
                        MockCalibrate.return_value = mock_calibrate

                        # Should not raise, even though calibration fails
                        result = await use_case_with_pacing.execute(
                            user_id=1,
                            fit_data=b"fake fit data",
                            source="upload",
                            source_ref="test.fit",
                        )

        # Ingestion should still succeed
        assert result is not None
        assert result.id == activity_with_power.id


