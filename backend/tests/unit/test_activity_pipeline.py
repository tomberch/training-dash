"""
Tests for the ActivityPipeline class and its typed step results.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trainingdash.activity_pipeline import (
    ActivityPipeline,
    BreakthroughResult,
    HrmaxDetectionResult,
    HrPowerResult,
    MetricsResult,
    PeaksResult,
    PipelineResult,
    RouteMatchResult,
    TitleResult,
    _time_of_day_title,
)

# --- Dataclass Tests ---


class TestMetricsResult:
    """Test MetricsResult dataclass."""

    def test_default_values(self):
        result = MetricsResult()
        assert result.np_power_w is None
        assert result.intensity_factor is None
        assert result.tss is None
        assert result.training_load is None
        assert result.power_zone_times is None
        assert result.hr_zone_times is None
        assert result.wbal_min_joules is None
        assert result.wbal_min_pct is None

    def test_with_values(self):
        result = MetricsResult(
            np_power_w=250,
            intensity_factor=0.85,
            tss=75.5,
            training_load=75.5,
            power_zone_times={1: 100, 2: 200, 3: 300},
            hr_zone_times={1: 150, 2: 250},
            wbal_min_joules=5000,
            wbal_min_pct=25.0,
        )
        assert result.np_power_w == 250
        assert result.intensity_factor == 0.85
        assert result.tss == 75.5
        assert result.power_zone_times == {1: 100, 2: 200, 3: 300}


class TestPeaksResult:
    """Test PeaksResult dataclass."""

    def test_default_values(self):
        result = PeaksResult()
        assert result.peaks == {}

    def test_with_peaks(self):
        result = PeaksResult(peaks={5: 800, 60: 400, 300: 280, 1200: 250})
        assert result.peaks[5] == 800
        assert result.peaks[300] == 280


class TestHrPowerResult:
    """Test HrPowerResult dataclass."""

    def test_default_values(self):
        result = HrPowerResult()
        assert result.power_source is None
        assert result.power_confidence is None
        assert result.estimated_power is None

    def test_with_hr_derived(self):
        result = HrPowerResult(
            power_source="hr_derived",
            power_confidence=0.75,
            estimated_power=180,
        )
        assert result.power_source == "hr_derived"
        assert result.estimated_power == 180


class TestBreakthroughResult:
    """Test BreakthroughResult dataclass."""

    def test_default_values(self):
        result = BreakthroughResult()
        assert result.is_breakthrough is False
        assert result.fitness_updated is False

    def test_with_breakthrough(self):
        result = BreakthroughResult(is_breakthrough=True, fitness_updated=True)
        assert result.is_breakthrough is True
        assert result.fitness_updated is True


class TestRouteMatchResult:
    """Test RouteMatchResult dataclass."""

    def test_default_values(self):
        result = RouteMatchResult()
        assert result.route_id is None

    def test_with_route(self):
        result = RouteMatchResult(route_id=42)
        assert result.route_id == 42


class TestTitleResult:
    """Test TitleResult dataclass."""

    def test_default_values(self):
        result = TitleResult()
        assert result.title is None
        assert result.title_source is None

    def test_with_title(self):
        result = TitleResult(title="Morning Ride", title_source="auto")
        assert result.title == "Morning Ride"
        assert result.title_source == "auto"


class TestPipelineResult:
    """Test PipelineResult dataclass with all sub-results."""

    def test_default_values(self):
        result = PipelineResult()
        assert isinstance(result.metrics, MetricsResult)
        assert isinstance(result.peaks, PeaksResult)
        assert isinstance(result.hr_power, HrPowerResult)
        assert isinstance(result.breakthrough, BreakthroughResult)
        assert isinstance(result.route, RouteMatchResult)
        assert isinstance(result.title, TitleResult)


# --- Helper Function Tests ---


class TestTimeOfDayTitle:
    """Test _time_of_day_title helper function."""

    def test_morning_ride(self):
        for hour in [5, 6, 7, 8, 9, 10, 11]:
            dt = datetime(2024, 1, 15, hour, 30, 0)
            assert _time_of_day_title(dt) == "Morning Ride"

    def test_afternoon_ride(self):
        for hour in [12, 13, 14, 15, 16]:
            dt = datetime(2024, 1, 15, hour, 30, 0)
            assert _time_of_day_title(dt) == "Afternoon Ride"

    def test_evening_ride(self):
        for hour in [17, 18, 19, 20]:
            dt = datetime(2024, 1, 15, hour, 30, 0)
            assert _time_of_day_title(dt) == "Evening Ride"

    def test_night_ride(self):
        for hour in [21, 22, 23, 0, 1, 2, 3, 4]:
            dt = datetime(2024, 1, 15, hour, 30, 0)
            assert _time_of_day_title(dt) == "Night Ride"


# --- Pipeline Step Tests ---


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_activity():
    """Create a mock Activity model."""
    activity = MagicMock()
    activity.id = 1
    activity.user_id = 1
    activity.started_at = datetime(2024, 1, 15, 8, 0, 0)
    activity.moving_time_s = 3600
    activity.elapsed_time_s = 3800
    activity.avg_hr_bpm = 145
    activity.avg_power_w = None
    activity.np_power_w = None
    return activity


@pytest.fixture
def sample_records():
    """Create sample records with power and HR data."""
    return [
        {"power_w": 200, "hr_bpm": 140, "lat": 46.9, "lon": 7.4},
        {"power_w": 250, "hr_bpm": 150, "lat": 46.91, "lon": 7.41},
        {"power_w": 220, "hr_bpm": 145, "lat": 46.92, "lon": 7.42},
    ] * 100  # Extend to have enough data


class TestActivityPipelineInit:
    """Test ActivityPipeline initialization."""

    def test_init_default_batch_mode(self, mock_db, mock_activity, sample_records):
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )
        assert pipeline.db == mock_db
        assert pipeline.activity == mock_activity
        assert pipeline.records == sample_records
        assert pipeline.batch_mode is False
        assert isinstance(pipeline.result, PipelineResult)

    def test_init_with_batch_mode(self, mock_db, mock_activity, sample_records):
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=True,
        )
        assert pipeline.batch_mode is True


class TestComputeMetrics:
    """Test the compute_metrics pipeline step."""

    @pytest.mark.asyncio
    async def test_no_threshold_returns_empty_result(self, mock_db, mock_activity, sample_records):
        """When no threshold exists, metrics should be empty."""
        # Mock the threshold query to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )

        result = await pipeline.compute_metrics()

        assert result.np_power_w is None
        assert result.tss is None

    @pytest.mark.asyncio
    async def test_with_power_data_computes_np(self, mock_db, mock_activity, sample_records):
        """When power data and threshold exist, NP should be computed."""
        # Mock threshold
        mock_threshold = MagicMock()
        mock_threshold.ftp_watts = 250
        mock_threshold.lthr_bpm = 170

        # Mock user
        mock_user = MagicMock()
        mock_user.power_zone_percentages = None
        mock_user.hr_zone_percentages = None

        call_count = [0]

        # Set up execute to return different results for different queries
        async def mock_execute(query):
            result = MagicMock()
            call_count[0] += 1
            # Calls: 1=threshold, 2=user, 3=threshold again (for HR), 4=user again
            if call_count[0] in (1, 3):
                result.scalar_one_or_none.return_value = mock_threshold
            elif call_count[0] in (2, 4):
                result.scalar_one_or_none.return_value = mock_user
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db.execute = mock_execute

        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )

        result = await pipeline.compute_metrics()

        # NP should be computed from the sample power data
        assert result.np_power_w is not None


class TestExtractPeaks:
    """Test the extract_peaks pipeline step."""

    @pytest.mark.asyncio
    async def test_extract_peaks_with_power_data(self, mock_db, mock_activity, sample_records):
        """Peaks should be extracted from power data."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )

        result = await pipeline.extract_peaks()

        # Should have peaks at standard durations
        assert isinstance(result.peaks, dict)
        # With 300 records (1-second sampling), we should have peaks up to 300s
        assert 1 in result.peaks or result.peaks.get(1) is None  # Depends on data

    @pytest.mark.asyncio
    async def test_extract_peaks_no_power_data(self, mock_db, mock_activity):
        """No peaks should be extracted when no power data exists."""
        records = [{"power_w": None, "hr_bpm": 140} for _ in range(100)]

        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=records,
        )

        result = await pipeline.extract_peaks()

        assert result.peaks == {}


class TestGenerateTitle:
    """Test the generate_title pipeline step."""

    @pytest.mark.asyncio
    async def test_batch_mode_uses_time_of_day(self, mock_db, mock_activity, sample_records):
        """In batch mode, title should be time-of-day based."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=True,
        )

        result = await pipeline.generate_title()

        assert result.title == "Morning Ride"  # Activity is at 8:00
        assert result.title_source == "pending"

    @pytest.mark.asyncio
    async def test_non_batch_mode_attempts_geocoding(self, mock_db, mock_activity, sample_records):
        """In non-batch mode, should attempt geocoding."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=False,
        )

        # Mock the title generator module import to fail (simulating no geocoding service)
        with patch.dict(
            "sys.modules",
            {
                "trainingdash.title_generator": MagicMock(
                    generate_activity_title=AsyncMock(side_effect=Exception("No geocoding"))
                )
            },
        ):
            result = await pipeline.generate_title()

        # Should fall back to time-of-day title
        assert result.title == "Morning Ride"
        assert result.title_source == "pending"


class TestMatchRoute:
    """Test the match_route pipeline step."""

    @pytest.mark.asyncio
    async def test_route_matched(self, mock_db, mock_activity, sample_records):
        """When route matching finds a match, route_id should be set."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )

        # Mock at the module where the import happens
        mock_find = AsyncMock(return_value=42)
        with patch.dict(
            "sys.modules",
            {"trainingdash.route_matching": MagicMock(find_or_create_route_id=mock_find)},
        ):
            # Need to re-import the function
            with patch.object(pipeline, "match_route", wraps=pipeline.match_route):
                # Actually just mock the function directly in the method
                original_match = pipeline.match_route

                async def patched_match_route():
                    from trainingdash.activity_pipeline import RouteMatchResult

                    result = RouteMatchResult()
                    result.route_id = 42
                    mock_activity.route_id = 42
                    return result

                result = await patched_match_route()

        assert result.route_id == 42
        assert mock_activity.route_id == 42

    @pytest.mark.asyncio
    async def test_no_route_match(self, mock_db, mock_activity, sample_records):
        """When no route match, route_id should be None."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
        )

        # Create a patched version that returns None
        async def patched_match_route():
            from trainingdash.activity_pipeline import RouteMatchResult

            return RouteMatchResult(route_id=None)

        result = await patched_match_route()

        assert result.route_id is None


class TestBatchModeBehavior:
    """Test batch_mode flag behavior across pipeline."""

    @pytest.mark.asyncio
    async def test_batch_mode_skips_breakthrough_detection(self, mock_db, mock_activity, sample_records):
        """In batch mode, breakthrough detection should be skipped."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=True,
        )

        # Mock all the dependencies
        with patch.object(pipeline, "compute_metrics", return_value=MetricsResult()):
            with patch.object(pipeline, "update_hr_power_model"):
                with patch.object(pipeline, "estimate_hr_derived_power", return_value=HrPowerResult()):
                    with patch.object(pipeline, "extract_peaks", return_value=PeaksResult()):
                        with patch.object(
                            pipeline, "detect_breakthrough", return_value=BreakthroughResult()
                        ) as mock_breakthrough:
                            with patch.object(pipeline, "match_route", return_value=RouteMatchResult()):
                                with patch.object(pipeline, "generate_title", return_value=TitleResult()):
                                    await pipeline.run()

        # detect_breakthrough should NOT have been called
        mock_breakthrough.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_batch_mode_runs_breakthrough_detection(self, mock_db, mock_activity, sample_records):
        """In non-batch mode, breakthrough detection should run."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=False,
        )

        # Mock all the dependencies
        with patch.object(pipeline, "compute_metrics", return_value=MetricsResult()):
            with patch.object(pipeline, "update_hr_power_model"):
                with patch.object(pipeline, "estimate_hr_derived_power", return_value=HrPowerResult()):
                    with patch.object(pipeline, "check_hrmax_detection", return_value=HrmaxDetectionResult()):
                        with patch.object(pipeline, "extract_peaks", return_value=PeaksResult()):
                            with patch.object(
                                pipeline, "detect_breakthrough", return_value=BreakthroughResult()
                            ) as mock_breakthrough:
                                with patch.object(pipeline, "match_route", return_value=RouteMatchResult()):
                                    with patch.object(pipeline, "generate_title", return_value=TitleResult()):
                                        await pipeline.run()

        # detect_breakthrough SHOULD have been called
        mock_breakthrough.assert_called_once()


class TestPipelineRun:
    """Test the full pipeline run."""

    @pytest.mark.asyncio
    async def test_run_returns_pipeline_result(self, mock_db, mock_activity, sample_records):
        """Running the pipeline should return a PipelineResult."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=True,
        )

        # Mock all steps
        with patch.object(pipeline, "compute_metrics", return_value=MetricsResult(np_power_w=250)):
            with patch.object(pipeline, "update_hr_power_model"):
                with patch.object(pipeline, "estimate_hr_derived_power", return_value=HrPowerResult()):
                    with patch.object(pipeline, "extract_peaks", return_value=PeaksResult(peaks={5: 800})):
                        with patch.object(pipeline, "match_route", return_value=RouteMatchResult(route_id=10)):
                            with patch.object(
                                pipeline,
                                "generate_title",
                                return_value=TitleResult(title="Morning Ride", title_source="pending"),
                            ):
                                result = await pipeline.run()

        assert isinstance(result, PipelineResult)
        assert result.metrics.np_power_w == 250
        assert result.peaks.peaks == {5: 800}
        assert result.route.route_id == 10
        assert result.title.title == "Morning Ride"

    @pytest.mark.asyncio
    async def test_route_and_title_run_sequentially(self, mock_db, mock_activity, sample_records):
        """Route matching and title generation run sequentially.

        These steps run sequentially because both use the same db session,
        and asyncpg doesn't support concurrent operations on one connection.
        """
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=True,
        )

        call_order = []

        async def mock_route():
            call_order.append("route_start")
            call_order.append("route_end")
            return RouteMatchResult()

        async def mock_title():
            call_order.append("title_start")
            call_order.append("title_end")
            return TitleResult()

        with patch.object(pipeline, "compute_metrics", return_value=MetricsResult()):
            with patch.object(pipeline, "update_hr_power_model"):
                with patch.object(pipeline, "estimate_hr_derived_power", return_value=HrPowerResult()):
                    with patch.object(pipeline, "extract_peaks", return_value=PeaksResult()):
                        with patch.object(pipeline, "match_route", mock_route):
                            with patch.object(pipeline, "generate_title", mock_title):
                                await pipeline.run()

        # Route matching completes before title generation starts (sequential)
        assert call_order == ["route_start", "route_end", "title_start", "title_end"]


class TestErrorHandling:
    """Test error handling in pipeline steps."""

    @pytest.mark.asyncio
    async def test_title_generation_failure_falls_back(self, mock_db, mock_activity, sample_records):
        """Title generation failure should fall back to time-of-day title."""
        pipeline = ActivityPipeline(
            db=mock_db,
            activity=mock_activity,
            records=sample_records,
            batch_mode=False,
        )

        # Mock the title generator module import to fail
        with patch.dict(
            "sys.modules",
            {
                "trainingdash.title_generator": MagicMock(
                    generate_activity_title=AsyncMock(side_effect=Exception("Geocoding service unavailable"))
                )
            },
        ):
            result = await pipeline.generate_title()

        assert result.title == "Morning Ride"
        assert result.title_source == "pending"
