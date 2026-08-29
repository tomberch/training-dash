"""Unit tests for CreateSegment use case."""

from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity, Record, Segment
from trainingdash.use_cases.create_segment import (
    CLIMB_MIN_GRADE_PCT,
    CLIMB_MIN_LENGTH_M,
    CreateSegment,
    CreateSegmentResult,
    DUPLICATE_OVERLAP_PCT,
    DUPLICATE_POINT_TOLERANCE_M,
    MAX_NAME_LENGTH,
    MIN_NAME_LENGTH,
    SPRINT_MAX_LENGTH_M,
    SPRINT_MIN_LENGTH_M,
)
from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.record_repo import FakeRecordRepo
from tests.fakes.segment_repos import FakeSegmentRepo


# =============================================================================
# Test Fixtures
# =============================================================================


def make_activity(user_id: int = 1, activity_id=None) -> Activity:
    """Create a test activity."""
    if activity_id is None:
        activity_id = uuid4()
    return Activity(
        id=activity_id,
        user_id=user_id,
        title="Test Ride",
        started_at=datetime(2024, 1, 15, 10, 0, 0),
        source="test",
        source_ref="test-123",
    )


def make_records(
    activity_id,
    coords: list[tuple[float, float, float, float]],
) -> list[Record]:
    """Create test records.

    Args:
        activity_id: Activity UUID
        coords: List of (lat, lon, altitude_m, distance_m) tuples
    """
    records = []
    for i, (lat, lon, altitude, distance) in enumerate(coords):
        records.append(
            Record(
                id=i + 1,
                activity_id=activity_id,
                timestamp=datetime(2024, 1, 15, 10, 0, i),
                lat=lat,
                lon=lon,
                altitude_m=altitude,
                distance_m=distance,
            )
        )
    return records


def make_climb_coords() -> list[tuple[float, float, float, float]]:
    """Create coordinates for a ~500m climb at ~8% grade (40m gain)."""
    # 500m at 8% = 40m elevation gain
    return [
        (47.0000, 8.0000, 500.0, 0.0),
        (47.0010, 8.0000, 510.0, 111.0),
        (47.0020, 8.0000, 520.0, 222.0),
        (47.0030, 8.0000, 530.0, 333.0),
        (47.0040, 8.0000, 540.0, 444.0),
        (47.0045, 8.0000, 540.0, 500.0),  # 500m total, 40m gain = 8%
    ]


def make_sprint_coords() -> list[tuple[float, float, float, float]]:
    """Create coordinates for a ~300m flat sprint."""
    return [
        (47.0000, 8.0000, 500.0, 0.0),
        (47.0010, 8.0000, 500.5, 111.0),
        (47.0020, 8.0000, 501.0, 222.0),
        (47.0027, 8.0000, 501.5, 300.0),  # 300m, ~0.5% grade
    ]


def make_custom_coords() -> list[tuple[float, float, float, float]]:
    """Create coordinates for a custom segment (not climb or sprint)."""
    # Long flat section - doesn't qualify as sprint (>600m) or climb (<3%)
    return [
        (47.0000, 8.0000, 500.0, 0.0),
        (47.0020, 8.0000, 501.0, 222.0),
        (47.0040, 8.0000, 502.0, 444.0),
        (47.0060, 8.0000, 503.0, 666.0),
        (47.0070, 8.0000, 503.5, 777.0),  # 777m, ~0.4% grade
    ]


# =============================================================================
# Happy Path Tests
# =============================================================================


class TestCreateSegmentHappyPath:
    """Tests for successful segment creation."""

    @pytest.mark.asyncio
    async def test_create_climb_segment(self):
        """Creates a climb segment with correct type and category."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Test Climb",
            )

        assert result.success is True
        assert result.segment is not None
        assert result.segment.name == "Test Climb"
        assert result.segment.type == "climb"
        assert result.segment.climb_category is not None
        assert result.segment.status == "approved"
        assert result.segment.created_by == 1
        assert result.segment.source_activity_id == activity.id

    @pytest.mark.asyncio
    async def test_create_sprint_segment(self):
        """Creates a sprint segment for flat 150-600m sections."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_sprint_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Sprint Zone",
            )

        assert result.success is True
        assert result.segment is not None
        assert result.segment.type == "sprint"
        assert result.segment.climb_category is None

    @pytest.mark.asyncio
    async def test_create_custom_segment(self):
        """Creates a custom segment for sections not matching climb/sprint criteria."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_custom_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Favorite Stretch",
            )

        assert result.success is True
        assert result.segment is not None
        assert result.segment.type == "custom"
        assert result.segment.climb_category is None

    @pytest.mark.asyncio
    async def test_enqueues_retroactive_match_job(self):
        """Enqueues retroactive match job after segment creation."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch(
            "trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock
        ) as mock_enqueue:
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Test Climb",
            )

        assert result.success is True
        mock_enqueue.assert_called_once_with(str(result.segment.id))

    @pytest.mark.asyncio
    async def test_segment_geometry_computed(self):
        """Computes geometry correctly from records."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Test Climb",
            )

        assert result.success is True
        segment = result.segment

        # Check geometry was computed
        assert segment.polyline is not None
        assert len(segment.polyline) > 0
        assert segment.distance_m > 0
        assert segment.elevation_gain_m >= 0
        assert segment.avg_grade_pct is not None
        assert segment.max_grade_pct is not None
        assert segment.direction_bearing is not None
        assert segment.gradient_segments is not None


# =============================================================================
# Error Cases
# =============================================================================


class TestCreateSegmentErrors:
    """Tests for error conditions."""

    @pytest.mark.asyncio
    async def test_activity_not_found(self):
        """Returns error when activity doesn't exist."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=uuid4(),
            start_index=0,
            end_index=10,
            name="Test Segment",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_activity_not_owned_by_user(self):
        """Returns error when activity belongs to different user."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=2)  # Different user
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,  # User 1 tries to access user 2's activity
            activity_id=activity.id,
            start_index=0,
            end_index=10,
            name="Test Segment",
        )

        assert result.success is False
        assert "not found" in result.error.lower() or "not owned" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_start_index_negative(self):
        """Returns error for negative start index."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=-1,
            end_index=10,
            name="Test Segment",
        )

        assert result.success is False
        assert "start index" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_end_index_before_start(self):
        """Returns error when end index is not greater than start."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=5,
            end_index=3,  # Before start
            name="Test Segment",
        )

        assert result.success is False
        assert "end index" in result.error.lower()

    @pytest.mark.asyncio
    async def test_end_index_exceeds_records(self):
        """Returns error when end index exceeds record count."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()  # 6 records
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=0,
            end_index=100,  # Exceeds record count
            name="Test Segment",
        )

        assert result.success is False
        assert "exceeds" in result.error.lower()

    @pytest.mark.asyncio
    async def test_activity_no_records(self):
        """Returns error when activity has no records."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)
        # Don't add any records

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=0,
            end_index=10,
            name="Test Segment",
        )

        assert result.success is False
        assert "no records" in result.error.lower()

    @pytest.mark.asyncio
    async def test_name_too_short(self):
        """Returns error when name is too short."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=0,
            end_index=10,
            name="AB",  # Too short
        )

        assert result.success is False
        assert str(MIN_NAME_LENGTH) in result.error

    @pytest.mark.asyncio
    async def test_name_too_long(self):
        """Returns error when name is too long."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=0,
            end_index=10,
            name="X" * (MAX_NAME_LENGTH + 1),  # Too long
        )

        assert result.success is False
        assert str(MAX_NAME_LENGTH) in result.error

    @pytest.mark.asyncio
    async def test_name_whitespace_only(self):
        """Returns error when name is only whitespace."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        result = await use_case.execute(
            user_id=1,
            activity_id=activity.id,
            start_index=0,
            end_index=10,
            name="   ",  # Only whitespace
        )

        assert result.success is False
        assert str(MIN_NAME_LENGTH) in result.error


# =============================================================================
# Duplicate Detection Tests
# =============================================================================


class TestDuplicateDetection:
    """Tests for duplicate segment detection."""

    @pytest.mark.asyncio
    async def test_duplicate_detected(self):
        """Detects duplicate when start/end within 25m and 95% overlap."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        # Create first segment
        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            first_result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Original Climb",
            )

        assert first_result.success is True
        original_segment = first_result.segment

        # Try to create duplicate with same coordinates
        # Need a second activity with same coords
        activity2 = make_activity(user_id=1)
        await activity_repo.save(activity2)
        records2 = make_records(activity2.id, coords)
        record_repo.add_many(records2)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            dup_result = await use_case.execute(
                user_id=1,
                activity_id=activity2.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Duplicate Climb",
            )

        assert dup_result.success is False
        assert "similar segment already exists" in dup_result.error.lower()
        assert dup_result.duplicate_segment_id == original_segment.id

    @pytest.mark.asyncio
    async def test_no_duplicate_different_location(self):
        """No duplicate detected for segments in different locations."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            first_result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="First Climb",
            )

        assert first_result.success is True

        # Create segment in completely different location
        activity2 = make_activity(user_id=1)
        await activity_repo.save(activity2)

        different_coords = [
            (48.0000, 9.0000, 500.0, 0.0),  # Far from original
            (48.0010, 9.0000, 510.0, 111.0),
            (48.0020, 9.0000, 520.0, 222.0),
            (48.0030, 9.0000, 530.0, 333.0),
            (48.0040, 9.0000, 540.0, 444.0),
            (48.0045, 9.0000, 540.0, 500.0),
        ]
        records2 = make_records(activity2.id, different_coords)
        record_repo.add_many(records2)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            second_result = await use_case.execute(
                user_id=1,
                activity_id=activity2.id,
                start_index=0,
                end_index=len(different_coords) - 1,
                name="Second Climb",
            )

        assert second_result.success is True


# =============================================================================
# Type Classification Tests
# =============================================================================


class TestTypeClassification:
    """Tests for segment type classification logic."""

    def test_classify_climb_cat4(self):
        """Classifies climb with Cat 4 category."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        # Cat 4: score >= 8000
        # 1000m at 8% = 8000
        seg_type, category = use_case._classify_segment(
            distance_m=1000, avg_grade_pct=8.0
        )

        assert seg_type == "climb"
        assert category == "4"

    def test_classify_climb_cat3(self):
        """Classifies climb with Cat 3 category."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        # Cat 3: score >= 16000
        # 2000m at 8% = 16000
        seg_type, category = use_case._classify_segment(
            distance_m=2000, avg_grade_pct=8.0
        )

        assert seg_type == "climb"
        assert category == "3"

    def test_classify_climb_hc(self):
        """Classifies climb with HC category."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        # HC: score >= 80000
        # 10000m at 8% = 80000
        seg_type, category = use_case._classify_segment(
            distance_m=10000, avg_grade_pct=8.0
        )

        assert seg_type == "climb"
        assert category == "hc"

    def test_classify_sprint(self):
        """Classifies sprint for 150-600m flat sections."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        seg_type, category = use_case._classify_segment(
            distance_m=300, avg_grade_pct=0.5
        )

        assert seg_type == "sprint"
        assert category is None

    def test_classify_sprint_boundary_min(self):
        """Sprint at minimum length boundary."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        seg_type, category = use_case._classify_segment(
            distance_m=SPRINT_MIN_LENGTH_M, avg_grade_pct=0.0
        )

        assert seg_type == "sprint"

    def test_classify_sprint_boundary_max(self):
        """Sprint at maximum length boundary."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        seg_type, category = use_case._classify_segment(
            distance_m=SPRINT_MAX_LENGTH_M, avg_grade_pct=0.0
        )

        assert seg_type == "sprint"

    def test_classify_custom_too_long_for_sprint(self):
        """Classifies as custom when too long for sprint but not steep enough for climb."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        seg_type, category = use_case._classify_segment(
            distance_m=1000, avg_grade_pct=1.0  # Too flat for climb, too long for sprint
        )

        assert seg_type == "custom"
        assert category is None

    def test_classify_custom_too_short_for_climb(self):
        """Classifies as custom when too short for climb criteria."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        # Steep but short
        seg_type, category = use_case._classify_segment(
            distance_m=200, avg_grade_pct=10.0  # Short steep section
        )

        assert seg_type == "custom"

    def test_classify_negative_grade_not_climb(self):
        """Descent doesn't classify as climb."""
        use_case = CreateSegment(
            FakeActivityRepo(), FakeRecordRepo(), FakeSegmentRepo()
        )

        seg_type, category = use_case._classify_segment(
            distance_m=1000, avg_grade_pct=-5.0  # Descent
        )

        assert seg_type == "custom"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_job_enqueue_failure_doesnt_fail_creation(self):
        """Segment creation succeeds even if job enqueue fails."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch(
            "trainingdash.use_cases.create_segment.enqueue_retroactive_match_job",
            new_callable=AsyncMock,
            side_effect=Exception("Queue unavailable"),
        ):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="Test Climb",
            )

        # Should still succeed
        assert result.success is True
        assert result.segment is not None

    @pytest.mark.asyncio
    async def test_name_trimmed(self):
        """Name whitespace is trimmed."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        coords = make_climb_coords()
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=0,
                end_index=len(coords) - 1,
                name="  Test Climb  ",  # Extra whitespace
            )

        assert result.success is True
        assert result.segment.name == "Test Climb"

    @pytest.mark.asyncio
    async def test_segment_subset_of_activity(self):
        """Can create segment from middle portion of activity."""
        activity_repo = FakeActivityRepo()
        record_repo = FakeRecordRepo()
        segment_repo = FakeSegmentRepo()

        activity = make_activity(user_id=1)
        await activity_repo.save(activity)

        # Longer activity with climb in the middle
        coords = [
            (47.0000, 8.0000, 500.0, 0.0),  # Warmup
            (47.0005, 8.0000, 500.0, 55.0),
            # Climb starts
            (47.0010, 8.0000, 510.0, 111.0),
            (47.0020, 8.0000, 520.0, 222.0),
            (47.0030, 8.0000, 530.0, 333.0),
            (47.0040, 8.0000, 540.0, 444.0),
            # Climb ends
            (47.0050, 8.0000, 540.0, 555.0),  # Cooldown
            (47.0060, 8.0000, 540.0, 666.0),
        ]
        records = make_records(activity.id, coords)
        record_repo.add_many(records)

        use_case = CreateSegment(activity_repo, record_repo, segment_repo)

        with patch("trainingdash.use_cases.create_segment.enqueue_retroactive_match_job", new_callable=AsyncMock):
            result = await use_case.execute(
                user_id=1,
                activity_id=activity.id,
                start_index=2,  # Start at climb
                end_index=5,  # End at climb
                name="Mid-Ride Climb",
            )

        assert result.success is True
        assert result.segment is not None
