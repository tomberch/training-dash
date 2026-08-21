"""Unit tests for CompareExecution use case."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.course_repo import FakeCourseRepo
from tests.fakes.race_plan_repo import FakeRacePlanRepo
from tests.fakes.record_repo import FakeRecordRepo
from trainingdash.repositories.postgres.models import (
    Activity,
    RaceCourse,
    RacePlan,
    Record,
)
from trainingdash.use_cases.compare_execution import (
    CompareExecution,
    ComparisonResult,
    SegmentComparison,
    generate_insights,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def plan_repo() -> FakeRacePlanRepo:
    return FakeRacePlanRepo()


@pytest.fixture
def activity_repo() -> FakeActivityRepo:
    return FakeActivityRepo()


@pytest.fixture
def record_repo() -> FakeRecordRepo:
    return FakeRecordRepo()


@pytest.fixture
def course_repo() -> FakeCourseRepo:
    return FakeCourseRepo()


@pytest.fixture
def use_case(
    plan_repo: FakeRacePlanRepo,
    activity_repo: FakeActivityRepo,
    record_repo: FakeRecordRepo,
    course_repo: FakeCourseRepo,
) -> CompareExecution:
    return CompareExecution(plan_repo, activity_repo, record_repo, course_repo)


@pytest.fixture
def sample_course(course_repo: FakeCourseRepo) -> RaceCourse:
    """Create a sample 10km course with 5 segments."""
    course = RaceCourse(
        user_id=1,
        name="Test Course",
        source_type="gpx",
        distance_m=10000,
        elevation_gain_m=200,
        elevation_loss_m=200,
        geometry="LINESTRING(0 0 0, 1 1 100)",  # Minimal valid geometry
        segments=[
            {"start_m": 0, "end_m": 2000, "distance_m": 2000, "avg_grade_pct": 0.0, "terrain_type": "flat"},
            {"start_m": 2000, "end_m": 4000, "distance_m": 2000, "avg_grade_pct": 5.0, "terrain_type": "climb"},
            {"start_m": 4000, "end_m": 6000, "distance_m": 2000, "avg_grade_pct": -5.0, "terrain_type": "descent"},
            {"start_m": 6000, "end_m": 8000, "distance_m": 2000, "avg_grade_pct": 3.0, "terrain_type": "false_flat"},
            {"start_m": 8000, "end_m": 10000, "distance_m": 2000, "avg_grade_pct": 0.0, "terrain_type": "flat"},
        ],
    )
    return course_repo.add(course)


@pytest.fixture
def sample_plan(plan_repo: FakeRacePlanRepo, sample_course: RaceCourse) -> RacePlan:
    """Create a sample plan with 5 segment targets."""
    plan = RacePlan(
        user_id=1,
        course_id=sample_course.id,
        rider_weight_kg=Decimal("75.0"),
        ftp_watts=250,
        cp_watts=240,
        w_prime_joules=20000,
        cda=Decimal("0.32"),
        crr=Decimal("0.004"),
        target_intensity=Decimal("0.85"),
        optimization_method="heuristic",
        total_time_s=1800.0,
        total_distance_m=10000.0,
        avg_power_w=210.0,
        segment_targets=[
            {"segment_idx": 0, "power_w": 200, "time_s": 300, "speed_mps": 6.67},
            {"segment_idx": 1, "power_w": 240, "time_s": 400, "speed_mps": 5.0},
            {"segment_idx": 2, "power_w": 180, "time_s": 250, "speed_mps": 8.0},
            {"segment_idx": 3, "power_w": 220, "time_s": 350, "speed_mps": 5.71},
            {"segment_idx": 4, "power_w": 200, "time_s": 300, "speed_mps": 6.67},
        ],
    )
    return plan_repo.add(plan)


@pytest.fixture
def sample_activity(activity_repo: FakeActivityRepo) -> Activity:
    """Create a sample activity."""
    activity = Activity(
        id=uuid4(),
        user_id=1,
        source="test",
        source_ref="test-123",
        started_at=datetime.now(),
        total_distance_m=10000,
        moving_time_s=1850,
        elapsed_time_s=1900,
        elevation_gain_m=200,
        avg_speed_mps=5.4,
        avg_power_w=215,
    )
    # Use direct dict access (FakeActivityRepo stores in _activities)
    activity_repo._activities[(activity.user_id, activity.id)] = activity
    return activity


def create_records_for_activity(
    record_repo: FakeRecordRepo,
    activity_id,
    start_time: datetime,
    segment_powers: list[tuple[float, float, int]],  # (start_m, end_m, power_w)
) -> list[Record]:
    """
    Create records matching segment boundaries with specified powers.

    Args:
        record_repo: Fake record repo
        activity_id: Activity UUID
        start_time: Activity start timestamp
        segment_powers: List of (start_m, end_m, power_w) tuples
    """
    records = []
    current_time = start_time
    distance = 0.0

    for start_m, end_m, power_w in segment_powers:
        segment_length = end_m - start_m
        # Create records every 100m within segment
        num_records = max(1, int(segment_length / 100))
        step_distance = segment_length / num_records
        step_time = timedelta(seconds=15)  # ~15s per 100m

        for i in range(num_records):
            distance = start_m + (i + 0.5) * step_distance
            record = Record(
                activity_id=activity_id,
                timestamp=current_time,
                distance_m=distance,
                power_w=power_w,
                speed_mps=6.0 + (power_w - 200) / 50,  # Approximate speed
            )
            records.append(record)
            current_time += step_time

    record_repo.add_many(records)
    return records


# =============================================================================
# Test CompareExecution Use Case
# =============================================================================


class TestCompareExecution:
    """Tests for the CompareExecution use case."""

    @pytest.mark.asyncio
    async def test_basic_comparison(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Basic comparison returns valid result structure."""
        # Create records with powers close to plan
        create_records_for_activity(
            record_repo,
            sample_activity.id,
            sample_activity.started_at,
            [
                (0, 2000, 205),  # Segment 0: +5W
                (2000, 4000, 235),  # Segment 1: -5W
                (4000, 6000, 185),  # Segment 2: +5W
                (6000, 8000, 225),  # Segment 3: +5W
                (8000, 10000, 195),  # Segment 4: -5W
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        assert isinstance(result, ComparisonResult)
        assert result.plan_id == sample_plan.id
        assert result.activity_id == sample_activity.id
        assert len(result.segment_comparisons) == 5
        assert result.avg_power_planned_w == 210.0
        assert result.pacing_consistency >= 0
        assert len(result.insights) > 0

    @pytest.mark.asyncio
    async def test_segment_deltas_calculated(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Power and time deltas are calculated for each segment."""
        create_records_for_activity(
            record_repo,
            sample_activity.id,
            sample_activity.started_at,
            [
                (0, 2000, 220),  # +20W = +10%
                (2000, 4000, 240),  # 0W = 0%
                (4000, 6000, 162),  # -18W = -10%
                (6000, 8000, 220),  # 0W = 0%
                (8000, 10000, 200),  # 0W = 0%
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        # Check first segment (planned 200W, actual ~220W)
        seg0 = result.segment_comparisons[0]
        assert seg0.planned_power_w == 200
        assert seg0.actual_power_w is not None
        assert abs(seg0.actual_power_w - 220) < 5  # Allow small variance
        assert seg0.power_delta_w is not None
        assert seg0.power_delta_pct is not None
        assert seg0.power_delta_pct > 5  # Should be ~10% over

    @pytest.mark.asyncio
    async def test_plan_not_found_raises(self, use_case: CompareExecution, sample_activity: Activity):
        """Raises ValueError when plan not found."""
        with pytest.raises(ValueError, match=r"Plan .* not found"):
            await use_case.execute(user_id=1, plan_id=999, activity_id=sample_activity.id)

    @pytest.mark.asyncio
    async def test_activity_not_found_raises(self, use_case: CompareExecution, sample_plan: RacePlan):
        """Raises ValueError when activity not found."""
        with pytest.raises(ValueError, match=r"Activity .* not found"):
            await use_case.execute(user_id=1, plan_id=sample_plan.id, activity_id=uuid4())

    @pytest.mark.asyncio
    async def test_no_records_raises(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
    ):
        """Raises ValueError when activity has no records."""
        # Don't add any records
        with pytest.raises(ValueError, match="Activity has no records"):
            await use_case.execute(
                user_id=1,
                plan_id=sample_plan.id,
                activity_id=sample_activity.id,
            )

    @pytest.mark.asyncio
    async def test_over_under_counts(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Segments over and under target are counted correctly."""
        # 2 over (+15%), 2 under (-15%), 1 on target
        create_records_for_activity(
            record_repo,
            sample_activity.id,
            sample_activity.started_at,
            [
                (0, 2000, 230),  # +30W = +15% OVER
                (2000, 4000, 276),  # +36W = +15% OVER
                (4000, 6000, 153),  # -27W = -15% UNDER
                (6000, 8000, 187),  # -33W = -15% UNDER
                (8000, 10000, 200),  # 0W = 0% ON TARGET
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        assert result.segments_over_target == 2
        assert result.segments_under_target == 2

    @pytest.mark.asyncio
    async def test_handles_missing_power_data(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Handles segments with no power data gracefully."""
        # Create records but only add power for some segments
        start_time = sample_activity.started_at
        current_time = start_time

        # Segment 0: has power
        for i in range(10):
            record_repo.add(
                Record(
                    activity_id=sample_activity.id,
                    timestamp=current_time,
                    distance_m=i * 200,
                    power_w=200,
                    speed_mps=6.0,
                )
            )
            current_time += timedelta(seconds=30)

        # Segment 1: no power (power_w=None)
        for i in range(10):
            record_repo.add(
                Record(
                    activity_id=sample_activity.id,
                    timestamp=current_time,
                    distance_m=2000 + i * 200,
                    power_w=None,  # No power data
                    speed_mps=5.0,
                )
            )
            current_time += timedelta(seconds=40)

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        # Should have segments_no_power > 0
        assert result.segments_no_power >= 1
        # First segment should have power
        assert result.segment_comparisons[0].actual_power_w is not None

    @pytest.mark.asyncio
    async def test_user_isolation(
        self,
        use_case: CompareExecution,
        plan_repo: FakeRacePlanRepo,
        activity_repo: FakeActivityRepo,
        course_repo: FakeCourseRepo,
        record_repo: FakeRecordRepo,
    ):
        """Cannot access other user's plans or activities."""
        # Create plan for user 1
        course = course_repo.add(
            RaceCourse(
                user_id=1,
                name="User 1 Course",
                source_type="gpx",
                distance_m=5000,
                elevation_gain_m=100,
                elevation_loss_m=100,
                geometry="LINESTRING(0 0 0, 1 1 100)",
                segments=[{"start_m": 0, "end_m": 5000, "distance_m": 5000, "avg_grade_pct": 0}],
            )
        )

        plan = plan_repo.add(
            RacePlan(
                user_id=1,
                course_id=course.id,
                rider_weight_kg=Decimal("75.0"),
                ftp_watts=250,
                cda=Decimal("0.32"),
                crr=Decimal("0.004"),
                total_time_s=600,
                total_distance_m=5000,
                avg_power_w=200,
                segment_targets=[{"segment_idx": 0, "power_w": 200, "time_s": 600, "speed_mps": 8.33}],
            )
        )

        # User 2 tries to access
        with pytest.raises(ValueError, match=r"Plan .* not found"):
            await use_case.execute(user_id=2, plan_id=plan.id, activity_id=uuid4())


class TestPacingConsistency:
    """Tests for pacing consistency calculation."""

    @pytest.mark.asyncio
    async def test_perfect_pacing_high_consistency(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Perfect pacing execution yields high consistency score."""
        # All segments exactly on target
        create_records_for_activity(
            record_repo,
            sample_activity.id,
            sample_activity.started_at,
            [
                (0, 2000, 200),
                (2000, 4000, 240),
                (4000, 6000, 180),
                (6000, 8000, 220),
                (8000, 10000, 200),
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        # Should be very high (close to 100)
        assert result.pacing_consistency > 90

    @pytest.mark.asyncio
    async def test_poor_pacing_low_consistency(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_activity: Activity,
        sample_course: RaceCourse,
        record_repo: FakeRecordRepo,
    ):
        """Poor pacing execution yields low consistency score."""
        # All segments way off target (±30%)
        create_records_for_activity(
            record_repo,
            sample_activity.id,
            sample_activity.started_at,
            [
                (0, 2000, 260),  # +30%
                (2000, 4000, 168),  # -30%
                (4000, 6000, 234),  # +30%
                (6000, 8000, 154),  # -30%
                (8000, 10000, 260),  # +30%
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=sample_activity.id,
        )

        # Should be low (well below 80)
        assert result.pacing_consistency < 80


class TestActivityLengthVariations:
    """Tests for activities shorter or longer than the course."""

    @pytest.mark.asyncio
    async def test_activity_shorter_than_course(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Handles activity that ends before completing the course."""
        # Create activity that only covers 6km of a 10km course
        short_activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-short",
            started_at=datetime.now(),
            total_distance_m=6000,  # Only 6km
            moving_time_s=1000,
            elapsed_time_s=1050,
            elevation_gain_m=150,
            avg_speed_mps=6.0,
            avg_power_w=210,
        )
        activity_repo._activities[(short_activity.user_id, short_activity.id)] = short_activity

        # Create records only for first 3 segments (0-6km)
        create_records_for_activity(
            record_repo,
            short_activity.id,
            short_activity.started_at,
            [
                (0, 2000, 200),
                (2000, 4000, 240),
                (4000, 6000, 180),
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=short_activity.id,
        )

        # Should still return 5 segment comparisons (plan has 5 segments)
        assert len(result.segment_comparisons) == 5
        # First 3 should have actual data
        assert result.segment_comparisons[0].actual_power_w is not None
        assert result.segment_comparisons[1].actual_power_w is not None
        assert result.segment_comparisons[2].actual_power_w is not None
        # Last 2 should have None (no records for those segments)
        assert result.segment_comparisons[3].actual_power_w is None
        assert result.segment_comparisons[4].actual_power_w is None

    @pytest.mark.asyncio
    async def test_activity_longer_than_course(
        self,
        use_case: CompareExecution,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Handles activity that continues beyond the course end."""
        # Create activity that covers 12km of a 10km course
        long_activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-long",
            started_at=datetime.now(),
            total_distance_m=12000,  # 12km, 2km beyond course
            moving_time_s=2200,
            elapsed_time_s=2300,
            elevation_gain_m=250,
            avg_speed_mps=5.5,
            avg_power_w=205,
        )
        activity_repo._activities[(long_activity.user_id, long_activity.id)] = long_activity

        # Create records for all 5 segments plus extra beyond course
        create_records_for_activity(
            record_repo,
            long_activity.id,
            long_activity.started_at,
            [
                (0, 2000, 200),
                (2000, 4000, 240),
                (4000, 6000, 180),
                (6000, 8000, 220),
                (8000, 10000, 200),
                (10000, 12000, 190),  # Beyond course end
            ],
        )

        result = await use_case.execute(
            user_id=1,
            plan_id=sample_plan.id,
            activity_id=long_activity.id,
        )

        # Should only compare the 5 course segments
        assert len(result.segment_comparisons) == 5
        # All segments should have data
        for comp in result.segment_comparisons:
            assert comp.actual_power_w is not None
        # Extra records beyond course should be ignored (not cause errors)


class TestGenerateInsights:
    """Tests for insight generation."""

    def test_started_too_fast_insight(self):
        """Detects starting too fast pattern."""
        comparisons = [
            SegmentComparison(0, 200, 240, 40, 20.0, 300, 280, -20, 6.67, 7.1, 0.43, 2000, 0.0),
            SegmentComparison(1, 240, 280, 40, 16.7, 400, 370, -30, 5.0, 5.4, 0.4, 2000, 5.0),
            SegmentComparison(2, 180, 180, 0, 0.0, 250, 250, 0, 8.0, 8.0, 0.0, 2000, -5.0),
            SegmentComparison(3, 220, 220, 0, 0.0, 350, 350, 0, 5.71, 5.71, 0.0, 2000, 3.0),
        ]
        segment_targets = [
            {"segment_idx": 0, "power_w": 200},
            {"segment_idx": 1, "power_w": 240},
            {"segment_idx": 2, "power_w": 180},
            {"segment_idx": 3, "power_w": 220},
        ]
        course_segments = [
            {"avg_grade_pct": 0.0},
            {"avg_grade_pct": 5.0},
            {"avg_grade_pct": -5.0},
            {"avg_grade_pct": 3.0},
        ]

        insights = generate_insights(comparisons, segment_targets, course_segments)

        assert any("Started too fast" in i or "over target" in i for i in insights)

    def test_faded_insight(self):
        """Detects fading at end pattern."""
        comparisons = [
            SegmentComparison(0, 200, 200, 0, 0.0, 300, 300, 0, 6.67, 6.67, 0.0, 2000, 0.0),
            SegmentComparison(1, 240, 240, 0, 0.0, 400, 400, 0, 5.0, 5.0, 0.0, 2000, 5.0),
            SegmentComparison(2, 180, 180, 0, 0.0, 250, 250, 0, 8.0, 8.0, 0.0, 2000, -5.0),
            SegmentComparison(3, 220, 176, -44, -20.0, 350, 400, 50, 5.71, 5.0, -0.71, 2000, 3.0),
        ]
        segment_targets = [{"segment_idx": i, "power_w": [200, 240, 180, 220][i]} for i in range(4)]
        course_segments = [{"avg_grade_pct": g} for g in [0, 5, -5, 3]]

        insights = generate_insights(comparisons, segment_targets, course_segments)

        assert any("Faded" in i or "under target" in i for i in insights)

    def test_good_climb_pacing_insight(self):
        """Detects good climb pacing."""
        comparisons = [
            SegmentComparison(0, 200, 200, 0, 0.0, 300, 300, 0, 6.67, 6.67, 0.0, 2000, 0.0),
            SegmentComparison(1, 240, 242, 2, 0.8, 400, 398, -2, 5.0, 5.0, 0.0, 2000, 6.0),
            SegmentComparison(2, 260, 258, -2, -0.8, 500, 502, 2, 4.0, 4.0, 0.0, 2000, 8.0),
        ]
        segment_targets = [{"segment_idx": i, "power_w": [200, 240, 260][i]} for i in range(3)]
        course_segments = [{"avg_grade_pct": g} for g in [0, 6, 8]]

        insights = generate_insights(comparisons, segment_targets, course_segments)

        assert any("climb" in i.lower() for i in insights)

    def test_empty_comparisons_returns_message(self):
        """Empty comparisons returns appropriate message."""
        insights = generate_insights([], [], [])

        assert len(insights) == 1
        assert "No comparison data" in insights[0]

    def test_no_power_returns_message(self):
        """Comparisons with no power data returns appropriate message."""
        comparisons = [
            SegmentComparison(0, 200, None, None, None, 300, 300, 0, 6.67, 6.67, None, 2000, 0.0),
            SegmentComparison(1, 240, None, None, None, 400, 400, 0, 5.0, 5.0, None, 2000, 5.0),
        ]

        insights = generate_insights(comparisons, [], [])

        assert any("No power data" in i for i in insights)

    def test_time_comparison_insight(self):
        """Generates time comparison insight."""
        comparisons = [
            SegmentComparison(0, 200, 210, 10, 5.0, 300, 280, -20, 6.67, 7.1, 0.43, 2000, 0.0),
            SegmentComparison(1, 240, 250, 10, 4.2, 400, 370, -30, 5.0, 5.4, 0.4, 2000, 5.0),
        ]
        segment_targets = [{"segment_idx": 0, "power_w": 200}, {"segment_idx": 1, "power_w": 240}]
        course_segments = [{"avg_grade_pct": 0}, {"avg_grade_pct": 5}]

        insights = generate_insights(comparisons, segment_targets, course_segments)

        # Should mention faster or slower
        assert any("faster" in i.lower() or "slower" in i.lower() for i in insights)
