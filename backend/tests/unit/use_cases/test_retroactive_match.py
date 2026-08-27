"""Unit tests for RetroactiveMatch use case."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from trainingdash.domain.segment_matching import SegmentMatch
from trainingdash.repositories.postgres.models import (
    Activity,
    Record,
    Segment,
    SegmentEffort,
)
from trainingdash.use_cases.retroactive_match import (
    DEFAULT_BATCH_SIZE,
    RetroactiveMatch,
    RetroactiveMatchResult,
)
from tests.fakes.segment_repos import FakeSegmentEffortRepo, FakeSegmentRepo


# =============================================================================
# Test Fixtures
# =============================================================================


def make_activity(
    user_id: int = 1,
    activity_id: UUID | None = None,
    direction_bearing: int = 90,
) -> Activity:
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
        direction_bearing=direction_bearing,
    )


def make_segment(
    segment_id: UUID | None = None,
    name: str = "Test Segment",
    direction_bearing: float = 90.0,
    status: str = "approved",
    matching_job_id: str | None = None,
) -> Segment:
    """Create a test segment with mock geometry."""
    if segment_id is None:
        segment_id = uuid4()

    # Create mock geometry objects
    mock_start = MagicMock()
    mock_end = MagicMock()
    mock_bounds = MagicMock()

    return Segment(
        id=segment_id,
        name=name,
        type="climb",
        status=status,
        polyline="_p~iF~ps|U",  # Sample polyline
        start_point=mock_start,
        end_point=mock_end,
        bounds=mock_bounds,
        direction_bearing=direction_bearing,
        distance_m=1000,
        elevation_gain_m=100,
        avg_grade_pct=10.0,
        max_grade_pct=15.0,
        gradient_segments=[],
        effort_count=0,
        athlete_count=0,
        matching_job_id=matching_job_id,
    )


def make_records_for_activity(
    activity_id: UUID,
    count: int = 3,
    base_time: datetime | None = None,
) -> list[dict]:
    """Create a list of record dicts for testing."""
    if base_time is None:
        base_time = datetime.now()

    records = []
    for i in range(count):
        records.append({
            "lat": 47.0 + (i * 0.005),
            "lon": 8.0,
            "altitude_m": 100.0 + (i * 10),
            "distance_m": i * 500.0,
            "timestamp": base_time + timedelta(seconds=i * 60),
            "power_w": 200 + (i * 25),
            "hr_bpm": 140 + (i * 5),
        })
    return records


# =============================================================================
# Test Cases
# =============================================================================


class TestRetroactiveMatchResult:
    """Tests for RetroactiveMatchResult dataclass."""

    def test_create_success_result(self):
        """Result can be created for success case."""
        result = RetroactiveMatchResult(
            success=True,
            activities_scanned=100,
            efforts_created=5,
        )
        assert result.success is True
        assert result.activities_scanned == 100
        assert result.efforts_created == 5
        assert result.error is None

    def test_create_failure_result(self):
        """Result can be created for failure case."""
        result = RetroactiveMatchResult(
            success=False,
            activities_scanned=50,
            efforts_created=2,
            error="Database error",
        )
        assert result.success is False
        assert result.activities_scanned == 50
        assert result.efforts_created == 2
        assert result.error == "Database error"


class TestRetroactiveMatch:
    """Tests for RetroactiveMatch use case."""

    @pytest.fixture
    def segment_repo(self):
        return FakeSegmentRepo()

    @pytest.fixture
    def effort_repo(self):
        return FakeSegmentEffortRepo()

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        return db

    @pytest.fixture
    def use_case(self, mock_db, segment_repo, effort_repo):
        return RetroactiveMatch(
            db=mock_db,
            segment_repo=segment_repo,
            effort_repo=effort_repo,
        )

    @pytest.mark.asyncio
    async def test_segment_not_found(self, use_case, segment_repo):
        """Returns error when segment not found."""
        result = await use_case.execute(uuid4())

        assert result.success is False
        assert result.error is not None
        assert "not found" in result.error
        assert result.activities_scanned == 0
        assert result.efforts_created == 0

    @pytest.mark.asyncio
    async def test_no_candidate_activities(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Returns success with zero counts when no activities match."""
        segment = make_segment()
        segment_repo.add(segment)

        with patch.object(use_case, "_find_candidate_activities", return_value=[]):
            with patch.object(use_case, "_build_segment_candidate"):
                with patch.object(use_case, "_update_segment_counts", return_value=None):
                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.activities_scanned == 0
        assert result.efforts_created == 0

    @pytest.mark.asyncio
    async def test_single_activity_matches(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Single activity matching creates one effort."""
        segment = make_segment()
        segment_repo.add(segment)

        activity = make_activity()
        records = make_records_for_activity(activity.id)

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )

        with patch.object(use_case, "_find_candidate_activities", side_effect=[[activity], []]):
            with patch.object(use_case, "_load_activity_records", return_value=records):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=False):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.activities_scanned == 1
        assert result.efforts_created == 1

        efforts = effort_repo.all()
        assert len(efforts) == 1
        assert efforts[0].segment_id == segment.id
        assert efforts[0].activity_id == activity.id
        assert efforts[0].is_pr is True

    @pytest.mark.asyncio
    async def test_batch_processing(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Activities are processed in batches."""
        segment = make_segment()
        segment_repo.add(segment)

        # Create activities for two batches
        batch1 = [make_activity(activity_id=uuid4()) for _ in range(3)]
        batch2 = [make_activity(activity_id=uuid4()) for _ in range(2)]

        def side_effect_candidates(segment, after_id, limit):
            if after_id is None:
                return batch1
            elif after_id == batch1[-1].id:
                return batch2
            return []

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )

        with patch.object(use_case, "_find_candidate_activities", side_effect=side_effect_candidates):
            with patch.object(use_case, "_load_activity_records", return_value=make_records_for_activity(uuid4())):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=False):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id, batch_size=3)

        assert result.success is True
        assert result.activities_scanned == 5
        assert result.efforts_created == 5

    @pytest.mark.asyncio
    async def test_no_duplicate_efforts(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Skips creating effort when one already exists."""
        segment = make_segment()
        segment_repo.add(segment)

        activity = make_activity()
        records = make_records_for_activity(activity.id)

        # Pre-existing effort
        existing_effort = SegmentEffort(
            id=uuid4(),
            segment_id=segment.id,
            activity_id=activity.id,
            user_id=activity.user_id,
            started_at=datetime.now(),
            elapsed_time_seconds=120,
            start_index=0,
            end_index=2,
            is_pr=True,
        )
        effort_repo.add(existing_effort)

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )

        with patch.object(use_case, "_find_candidate_activities", side_effect=[[activity], []]):
            with patch.object(use_case, "_load_activity_records", return_value=records):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=True):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.activities_scanned == 1
        assert result.efforts_created == 0

        # Should still only have the pre-existing effort
        assert len(effort_repo.all()) == 1

    @pytest.mark.asyncio
    async def test_pr_flags_updated_correctly(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """PR flags are updated when faster time is found."""
        segment = make_segment()
        segment_repo.add(segment)

        # Two activities from same user with different times
        activity1 = make_activity(user_id=1, activity_id=uuid4())
        activity2 = make_activity(user_id=1, activity_id=uuid4())

        # Activity 1: slower (120 seconds)
        records1 = make_records_for_activity(activity1.id, base_time=datetime(2024, 1, 1, 10, 0))
        # Activity 2: faster (60 seconds)
        base_time2 = datetime(2024, 1, 2, 10, 0)
        records2 = [
            {"lat": 47.0, "lon": 8.0, "altitude_m": 100, "distance_m": 0, "timestamp": base_time2, "power_w": 200, "hr_bpm": 140},
            {"lat": 47.01, "lon": 8.0, "altitude_m": 110, "distance_m": 1000, "timestamp": base_time2 + timedelta(seconds=60), "power_w": 250, "hr_bpm": 150},
        ]

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=1,
            overlap_pct=95.0,
        )

        activities = [activity1, activity2]
        records_map = {activity1.id: records1, activity2.id: records2}

        def load_records(activity_id):
            return records_map.get(activity_id, [])

        with patch.object(use_case, "_find_candidate_activities", side_effect=[activities, []]):
            with patch.object(use_case, "_load_activity_records", side_effect=load_records):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=False):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.efforts_created == 2

        efforts = effort_repo.all()
        pr_efforts = [e for e in efforts if e.is_pr]
        # Only one PR should exist (the faster one)
        assert len(pr_efforts) == 1
        assert pr_efforts[0].elapsed_time_seconds == 60

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Resuming from checkpoint skips already-processed activities."""
        # Segment with checkpoint set
        checkpoint_activity_id = uuid4()
        segment = make_segment(
            matching_job_id=f"job123:{checkpoint_activity_id}",
        )
        segment_repo.add(segment)

        # Activity that should be processed (after checkpoint)
        activity = make_activity(activity_id=uuid4())
        records = make_records_for_activity(activity.id)

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )

        call_count = [0]
        # Should start after the checkpoint
        def side_effect_candidates(*args, **kwargs):
            call_count[0] += 1
            after_id = kwargs.get("after_id")
            if after_id == checkpoint_activity_id:
                return [activity]
            return []

        with patch.object(use_case, "_find_candidate_activities", side_effect=side_effect_candidates):
            with patch.object(use_case, "_load_activity_records", return_value=records):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=False):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.activities_scanned == 1
        assert result.efforts_created == 1

    @pytest.mark.asyncio
    async def test_skip_activity_with_insufficient_records(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Skips activities with fewer than 2 records."""
        segment = make_segment()
        segment_repo.add(segment)

        activity = make_activity()
        # Only 1 record - insufficient
        single_record = [{"lat": 47.0, "lon": 8.0, "altitude_m": 100, "distance_m": 0, "timestamp": datetime.now(), "power_w": None, "hr_bpm": None}]

        with patch.object(use_case, "_find_candidate_activities", side_effect=[[activity], []]):
            with patch.object(use_case, "_load_activity_records", return_value=single_record):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch.object(use_case, "_update_segment_counts", return_value=None):
                        with patch.object(use_case, "_set_checkpoint", return_value=None):
                            result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.activities_scanned == 1
        assert result.efforts_created == 0  # No effort created

    @pytest.mark.asyncio
    async def test_multiple_users_pr_tracking(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """PR flags are tracked per-user correctly."""
        segment = make_segment()
        segment_repo.add(segment)

        # Activities from different users
        activity1 = make_activity(user_id=1)
        activity2 = make_activity(user_id=2)
        records = make_records_for_activity(uuid4())

        match = SegmentMatch(
            segment_id=segment.id,
            start_index=0,
            end_index=2,
            overlap_pct=95.0,
        )

        with patch.object(use_case, "_find_candidate_activities", side_effect=[[activity1, activity2], []]):
            with patch.object(use_case, "_load_activity_records", return_value=records):
                with patch.object(use_case, "_build_segment_candidate"):
                    with patch(
                        "trainingdash.use_cases.retroactive_match.match_activity_to_segments",
                        return_value=[match],
                    ):
                        with patch.object(use_case, "_check_existing_effort", return_value=False):
                            with patch.object(use_case, "_update_segment_counts", return_value=None):
                                with patch.object(use_case, "_set_checkpoint", return_value=None):
                                    result = await use_case.execute(segment.id)

        assert result.success is True
        assert result.efforts_created == 2

        efforts = effort_repo.all()
        # Both should be PRs since they're from different users
        assert all(e.is_pr for e in efforts)

    @pytest.mark.asyncio
    async def test_updates_denormalized_counts(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """Segment counts are updated after completion."""
        segment = make_segment()
        segment_repo.add(segment)

        with patch.object(use_case, "_find_candidate_activities", return_value=[]):
            with patch.object(use_case, "_build_segment_candidate"):
                with patch.object(use_case, "_update_segment_counts", return_value=None) as mock_update:
                    result = await use_case.execute(segment.id)

        assert result.success is True
        mock_update.assert_called_once_with(segment.id)

    @pytest.mark.asyncio
    async def test_clears_matching_job_id_on_completion(
        self, use_case, mock_db, segment_repo, effort_repo
    ):
        """matching_job_id is cleared after successful completion."""
        segment = make_segment()
        segment_repo.add(segment)

        with patch.object(use_case, "_find_candidate_activities", return_value=[]):
            with patch.object(use_case, "_build_segment_candidate"):
                with patch.object(use_case, "_update_segment_counts", return_value=None):
                    with patch.object(use_case, "_clear_matching_job_id", return_value=None) as mock_clear:
                        result = await use_case.execute(segment.id)

        assert result.success is True
        mock_clear.assert_called_once_with(segment.id)


class TestHelperMethods:
    """Tests for helper methods."""

    @pytest.fixture
    def use_case(self):
        return RetroactiveMatch(
            db=AsyncMock(),
            segment_repo=FakeSegmentRepo(),
            effort_repo=FakeSegmentEffortRepo(),
        )

    def test_compute_avg_power_with_values(self, use_case):
        """Computes average power correctly."""
        records = [
            {"power_w": 200},
            {"power_w": 250},
            {"power_w": 300},
        ]
        avg = use_case._compute_avg_power(records)
        assert avg == 250

    def test_compute_avg_power_with_none(self, use_case):
        """Returns None when no power data."""
        records = [
            {"power_w": None},
            {"power_w": None},
        ]
        avg = use_case._compute_avg_power(records)
        assert avg is None

    def test_compute_avg_power_partial_data(self, use_case):
        """Computes average from available power data only."""
        records = [
            {"power_w": 200},
            {"power_w": None},
            {"power_w": 300},
        ]
        avg = use_case._compute_avg_power(records)
        assert avg == 250  # (200 + 300) / 2

    def test_compute_avg_hr_with_values(self, use_case):
        """Computes average HR correctly."""
        records = [
            {"hr_bpm": 140},
            {"hr_bpm": 150},
            {"hr_bpm": 160},
        ]
        avg = use_case._compute_avg_hr(records)
        assert avg == 150

    def test_compute_avg_hr_with_none(self, use_case):
        """Returns None when no HR data."""
        records = [
            {"hr_bpm": None},
            {"hr_bpm": None},
        ]
        avg = use_case._compute_avg_hr(records)
        assert avg is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_no_job_id(self, use_case):
        """Returns None when no matching_job_id set."""
        segment = make_segment(matching_job_id=None)
        checkpoint = await use_case._get_checkpoint(segment)
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_job_id_only(self, use_case):
        """Returns None when job_id has no checkpoint."""
        segment = make_segment(matching_job_id="job123")
        checkpoint = await use_case._get_checkpoint(segment)
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_get_checkpoint_with_activity_id(self, use_case):
        """Returns activity ID from checkpoint."""
        activity_id = uuid4()
        segment = make_segment(matching_job_id=f"job123:{activity_id}")
        checkpoint = await use_case._get_checkpoint(segment)
        assert checkpoint == activity_id

    @pytest.mark.asyncio
    async def test_get_checkpoint_invalid_uuid(self, use_case):
        """Returns None for invalid UUID in checkpoint."""
        segment = make_segment(matching_job_id="job123:not-a-uuid")
        checkpoint = await use_case._get_checkpoint(segment)
        assert checkpoint is None


class TestDirectionFiltering:
    """Tests for direction bearing filtering logic."""

    def test_default_batch_size(self):
        """Default batch size is 100."""
        assert DEFAULT_BATCH_SIZE == 100
