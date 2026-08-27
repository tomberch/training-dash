"""Unit tests for ProcessActivitySegments use case."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from trainingdash.domain.climb_detection import DetectedClimb
from trainingdash.domain.segment_geometry import GradientSegment
from trainingdash.domain.segment_matching import SegmentCandidate, SegmentMatch
from trainingdash.repositories.postgres.models import (
    Activity,
    Record,
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)
from trainingdash.use_cases.process_activity_segments import (
    ProcessActivitySegments,
    ProcessResult,
)
from tests.fakes.segment_repos import (
    FakeSegmentEffortRepo,
    FakeSegmentRepo,
    FakeSegmentSuggestionRepo,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def setup_mock_db(mock_db, activity: Activity | None, records: list[Record]) -> None:
    """Configure mock_db to return activity and records."""
    mock_result_activity = MagicMock()
    mock_result_activity.scalar_one_or_none.return_value = activity
    
    mock_result_records = MagicMock()
    mock_result_records.scalars.return_value.all.return_value = records
    
    mock_db.execute = AsyncMock(side_effect=[mock_result_activity, mock_result_records])


def make_activity(user_id: int = 1, activity_id=None) -> Activity:
    """Create a test activity."""
    if activity_id is None:
        activity_id = uuid4()
    
    return Activity(
        id=activity_id,
        user_id=user_id,
        source="test",
        source_ref="test-123",
        started_at=datetime.now(),
        elapsed_time_s=3600,
        total_distance_m=10000,
    )


def make_record(
    activity_id,
    lat: float,
    lon: float,
    distance_m: float,
    altitude_m: float = 100.0,
    timestamp: datetime = None,
    power_w: int | None = None,
    hr_bpm: int | None = None,
) -> Record:
    """Create a test record."""
    if timestamp is None:
        timestamp = datetime.now()
    
    return Record(
        activity_id=activity_id,
        lat=lat,
        lon=lon,
        distance_m=distance_m,
        altitude_m=altitude_m,
        timestamp=timestamp,
        power_w=power_w,
        hr_bpm=hr_bpm,
    )


def make_segment(
    segment_id=None,
    name: str = "Test Segment",
    type: str = "climb",
    status: str = "approved",
) -> Segment:
    """Create a test segment."""
    if segment_id is None:
        segment_id = uuid4()
    
    return Segment(
        id=segment_id,
        name=name,
        type=type,
        status=status,
        polyline="test_polyline",
        start_point=MagicMock(),
        end_point=MagicMock(),
        bounds=MagicMock(),
        direction_bearing=0.0,
        distance_m=1000,
        elevation_gain_m=100,
        avg_grade_pct=10.0,
        max_grade_pct=15.0,
        gradient_segments=[],
        effort_count=0,
        athlete_count=0,
    )


def make_segment_candidate(segment: Segment) -> SegmentCandidate:
    """Create a SegmentCandidate from a Segment."""
    return SegmentCandidate(
        id=segment.id,
        polyline=segment.polyline,
        start_lat=47.0,
        start_lon=8.0,
        end_lat=47.01,
        end_lon=8.0,
        direction_bearing=segment.direction_bearing or 0.0,
        distance_m=segment.distance_m,
    )


# =============================================================================
# Test Cases
# =============================================================================


class TestProcessResult:
    """Tests for ProcessResult dataclass."""

    def test_create_result(self):
        """ProcessResult can be created with all fields."""
        result = ProcessResult(
            matched_efforts=5,
            detected_climbs=2,
            new_prs=1,
        )
        assert result.matched_efforts == 5
        assert result.detected_climbs == 2
        assert result.new_prs == 1


class TestProcessActivitySegments:
    """Tests for ProcessActivitySegments use case."""

    @pytest.fixture
    def segment_repo(self):
        return FakeSegmentRepo()

    @pytest.fixture
    def effort_repo(self):
        return FakeSegmentEffortRepo()

    @pytest.fixture
    def suggestion_repo(self):
        return FakeSegmentSuggestionRepo()

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_db, segment_repo, effort_repo, suggestion_repo):
        return ProcessActivitySegments(
            db=mock_db,
            segment_repo=segment_repo,
            effort_repo=effort_repo,
            suggestion_repo=suggestion_repo,
        )

    @pytest.mark.asyncio
    async def test_activity_not_found(self, use_case, mock_db):
        """Returns empty result when activity not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        result = await use_case.execute(uuid4(), user_id=1)
        
        assert result.matched_efforts == 0
        assert result.detected_climbs == 0
        assert result.new_prs == 0

    @pytest.mark.asyncio
    async def test_insufficient_records(self, use_case, mock_db):
        """Returns empty result when activity has < 2 records."""
        activity = make_activity()
        records = [make_record(activity.id, 47.0, 8.0, 0)]
        
        setup_mock_db(mock_db, activity, records)
        
        result = await use_case.execute(activity.id, user_id=1)
        
        assert result.matched_efforts == 0
        assert result.detected_climbs == 0
        assert result.new_prs == 0

    @pytest.mark.asyncio
    async def test_match_single_segment_creates_effort(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Matching a segment creates a SegmentEffort."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, timestamp=base_time),
            make_record(activity.id, 47.005, 8.0, 500, timestamp=base_time + timedelta(seconds=60)),
            make_record(activity.id, 47.01, 8.0, 1000, timestamp=base_time + timedelta(seconds=120)),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        segment = make_segment()
        segment_repo.add(segment)
        
        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )
        
        with patch.object(use_case, "_find_candidates", return_value=[make_segment_candidate(segment)]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[match]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[]):
                    result = await use_case.execute(activity.id, user_id=1)
        
        assert result.matched_efforts == 1
        assert result.new_prs == 1
        
        efforts = effort_repo.all()
        assert len(efforts) == 1
        assert efforts[0].segment_id == segment.id
        assert efforts[0].is_pr is True

    @pytest.mark.asyncio
    async def test_match_multiple_segments(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Matching multiple segments creates multiple efforts."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, timestamp=base_time),
            make_record(activity.id, 47.01, 8.0, 1000, timestamp=base_time + timedelta(seconds=120)),
            make_record(activity.id, 47.02, 8.0, 2000, timestamp=base_time + timedelta(seconds=240)),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        segment1 = make_segment(name="Segment 1")
        segment2 = make_segment(name="Segment 2")
        segment_repo.add(segment1)
        segment_repo.add(segment2)
        
        matches = [
            SegmentMatch(segment_id=segment1.id, start_index=0, end_index=1, overlap_pct=95.0),
            SegmentMatch(segment_id=segment2.id, start_index=1, end_index=2, overlap_pct=92.0),
        ]
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=matches):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[]):
                    result = await use_case.execute(activity.id, user_id=1)
        
        assert result.matched_efforts == 2
        assert result.new_prs == 2
        assert len(effort_repo.all()) == 2

    @pytest.mark.asyncio
    async def test_new_pr_updates_flags(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """New PR clears old PR flag and sets new one."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, timestamp=base_time),
            make_record(activity.id, 47.01, 8.0, 1000, timestamp=base_time + timedelta(seconds=60)),  # Faster!
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        segment = make_segment()
        segment_repo.add(segment)
        
        # Add existing PR effort (slower - 120 seconds)
        old_effort = SegmentEffort(
            id=uuid4(),
            segment_id=segment.id,
            activity_id=uuid4(),
            user_id=1,
            started_at=datetime.now(),
            elapsed_time_seconds=120,
            start_index=0,
            end_index=1,
            is_pr=True,
        )
        effort_repo.add(old_effort)
        
        match = SegmentMatch(segment_id=segment.id, start_index=0, end_index=1, overlap_pct=95.0)
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[match]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[]):
                    result = await use_case.execute(activity.id, user_id=1)
        
        assert result.new_prs == 1
        
        efforts = effort_repo.all()
        pr_efforts = [e for e in efforts if e.is_pr]
        assert len(pr_efforts) == 1
        assert pr_efforts[0].elapsed_time_seconds == 60  # The faster one

    @pytest.mark.asyncio
    async def test_detect_climb_creates_suggestion(
        self, use_case, mock_db, segment_repo, suggestion_repo
    ):
        """Detecting a climb creates a segment suggestion."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, altitude_m=100, timestamp=base_time),
            make_record(activity.id, 47.005, 8.0, 500, altitude_m=150, timestamp=base_time + timedelta(seconds=60)),
            make_record(activity.id, 47.01, 8.0, 1000, altitude_m=200, timestamp=base_time + timedelta(seconds=120)),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        detected_climb = DetectedClimb(
            start_index=0,
            end_index=2,
            distance_m=1000,
            elevation_gain_m=100,
            avg_grade_pct=10.0,
            max_grade_pct=12.0,
            category="4",
            gradient_segments=[GradientSegment(distance_m=500, grade_pct=10.0)],
        )
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[detected_climb]):
                    result = await use_case.execute(activity.id, user_id=1)
        
        assert result.detected_climbs == 1
        
        suggestions = suggestion_repo.all()
        assert len(suggestions) == 1
        assert suggestions[0].user_id == 1
        assert suggestions[0].repetition_count == 1

    @pytest.mark.asyncio
    async def test_skip_climb_detection_when_overlaps_segment(
        self, use_case, mock_db, segment_repo, effort_repo, suggestion_repo
    ):
        """Skip climb detection when it overlaps an existing matched segment."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, altitude_m=100, timestamp=base_time),
            make_record(activity.id, 47.01, 8.0, 1000, altitude_m=200, timestamp=base_time + timedelta(seconds=120)),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        segment = make_segment()
        segment_repo.add(segment)
        
        match = SegmentMatch(segment_id=segment.id, start_index=0, end_index=1, overlap_pct=95.0)
        
        detected_climb = DetectedClimb(
            start_index=0,
            end_index=1,
            distance_m=1000,
            elevation_gain_m=100,
            avg_grade_pct=10.0,
            max_grade_pct=12.0,
            category="4",
            gradient_segments=[],
        )
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[match]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[detected_climb]):
                    with patch("trainingdash.use_cases.process_activity_segments.compute_path_overlap", return_value=85.0):
                        result = await use_case.execute(activity.id, user_id=1)
        
        assert result.matched_efforts == 1
        assert result.detected_climbs == 0  # Skipped because of overlap
        assert len(suggestion_repo.all()) == 0

    @pytest.mark.asyncio
    async def test_no_segments_or_climbs_flat_ride(
        self, use_case, mock_db, segment_repo, effort_repo, suggestion_repo
    ):
        """Flat ride with no segments returns empty result."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, altitude_m=100, timestamp=base_time),
            make_record(activity.id, 47.01, 8.0, 1000, altitude_m=100, timestamp=base_time + timedelta(seconds=120)),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[]):
                    result = await use_case.execute(activity.id, user_id=1)
        
        assert result.matched_efforts == 0
        assert result.detected_climbs == 0
        assert result.new_prs == 0

    @pytest.mark.asyncio
    async def test_effort_calculates_avg_power_and_hr(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Effort correctly calculates average power and HR."""
        activity = make_activity()
        base_time = datetime.now()
        records = [
            make_record(activity.id, 47.0, 8.0, 0, timestamp=base_time, power_w=200, hr_bpm=140),
            make_record(activity.id, 47.005, 8.0, 500, timestamp=base_time + timedelta(seconds=60), power_w=250, hr_bpm=150),
            make_record(activity.id, 47.01, 8.0, 1000, timestamp=base_time + timedelta(seconds=120), power_w=300, hr_bpm=160),
        ]
        
        setup_mock_db(mock_db, activity, records)
        
        segment = make_segment()
        segment_repo.add(segment)
        
        match = SegmentMatch(segment_id=segment.id, start_index=0, end_index=2, overlap_pct=95.0)
        
        with patch.object(use_case, "_find_candidates", return_value=[]):
            with patch("trainingdash.use_cases.process_activity_segments.match_activity_to_segments", return_value=[match]):
                with patch("trainingdash.use_cases.process_activity_segments.detect_climbs", return_value=[]):
                    await use_case.execute(activity.id, user_id=1)
        
        efforts = effort_repo.all()
        assert len(efforts) == 1
        assert efforts[0].avg_power_watts == 250  # (200 + 250 + 300) / 3
        assert efforts[0].avg_hr_bpm == 150  # (140 + 150 + 160) / 3


class TestHelperMethods:
    """Tests for helper methods."""

    def test_compute_avg_power_with_values(self):
        """Computes average power correctly."""
        use_case = ProcessActivitySegments(
            db=AsyncMock(),
            segment_repo=FakeSegmentRepo(),
            effort_repo=FakeSegmentEffortRepo(),
            suggestion_repo=FakeSegmentSuggestionRepo(),
        )
        
        records = [
            {"power_w": 200},
            {"power_w": 250},
            {"power_w": 300},
        ]
        
        avg = use_case._compute_avg_power(records)
        assert avg == 250

    def test_compute_avg_power_with_none(self):
        """Returns None when no power data."""
        use_case = ProcessActivitySegments(
            db=AsyncMock(),
            segment_repo=FakeSegmentRepo(),
            effort_repo=FakeSegmentEffortRepo(),
            suggestion_repo=FakeSegmentSuggestionRepo(),
        )
        
        records = [
            {"power_w": None},
            {"power_w": None},
        ]
        
        avg = use_case._compute_avg_power(records)
        assert avg is None

    def test_compute_avg_hr_with_values(self):
        """Computes average HR correctly."""
        use_case = ProcessActivitySegments(
            db=AsyncMock(),
            segment_repo=FakeSegmentRepo(),
            effort_repo=FakeSegmentEffortRepo(),
            suggestion_repo=FakeSegmentSuggestionRepo(),
        )
        
        records = [
            {"hr_bpm": 140},
            {"hr_bpm": 150},
            {"hr_bpm": 160},
        ]
        
        avg = use_case._compute_avg_hr(records)
        assert avg == 150

    def test_prepare_records_filters_null_coords(self):
        """Prepare records filters out records without coordinates."""
        use_case = ProcessActivitySegments(
            db=AsyncMock(),
            segment_repo=FakeSegmentRepo(),
            effort_repo=FakeSegmentEffortRepo(),
            suggestion_repo=FakeSegmentSuggestionRepo(),
        )
        
        activity = make_activity()
        records_list = [
            make_record(activity.id, 47.0, 8.0, 0),
            Record(activity_id=activity.id, lat=None, lon=None, distance_m=500, timestamp=datetime.now()),
            make_record(activity.id, 47.01, 8.0, 1000),
        ]
        
        records = use_case._prepare_records(records_list)
        assert len(records) == 2
        assert all(r["lat"] is not None for r in records)
