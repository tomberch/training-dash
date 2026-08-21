"""Unit tests for GetMatchingActivities use case."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity, RaceCourse, RacePlan
from trainingdash.use_cases.get_matching_activities import (
    GetMatchingActivities,
    MatchingActivity,
)
from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.course_repo import FakeCourseRepo
from tests.fakes.race_plan_repo import FakeRacePlanRepo


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def activity_repo() -> FakeActivityRepo:
    return FakeActivityRepo()


@pytest.fixture
def plan_repo() -> FakeRacePlanRepo:
    return FakeRacePlanRepo()


@pytest.fixture
def course_repo() -> FakeCourseRepo:
    return FakeCourseRepo()


@pytest.fixture
def use_case(
    plan_repo: FakeRacePlanRepo,
    activity_repo: FakeActivityRepo,
    course_repo: FakeCourseRepo,
) -> GetMatchingActivities:
    return GetMatchingActivities(plan_repo, activity_repo, course_repo)


@pytest.fixture
def sample_course(course_repo: FakeCourseRepo) -> RaceCourse:
    """Create a 50km course."""
    course = RaceCourse(
        user_id=1,
        name="Test Course",
        source_type="gpx",
        distance_m=50000,  # 50km
        elevation_gain_m=500,
        elevation_loss_m=500,
        geometry="LINESTRING(0 0 0, 1 1 100)",
        segments=[],
    )
    return course_repo.add(course)


@pytest.fixture
def sample_plan(plan_repo: FakeRacePlanRepo, sample_course: RaceCourse) -> RacePlan:
    """Create a race plan for the 50km course."""
    plan = RacePlan(
        user_id=1,
        course_id=sample_course.id,
        rider_weight_kg=Decimal("75.0"),
        ftp_watts=250,
        cda=Decimal("0.32"),
        crr=Decimal("0.004"),
        total_time_s=5400.0,  # 1.5 hours
        total_distance_m=50000.0,
        avg_power_w=220.0,
        segment_targets=[],
    )
    return plan_repo.add(plan)


def create_activity(
    user_id: int,
    distance_m: float,
    avg_power_w: float | None,
    started_at: datetime | None = None,
    title: str | None = None,
) -> Activity:
    """Helper to create an activity."""
    return Activity(
        id=uuid4(),
        user_id=user_id,
        source="test",
        source_ref=f"test-{uuid4().hex[:8]}",
        started_at=started_at or datetime.now(),
        total_distance_m=distance_m,
        moving_time_s=int(distance_m / 8),  # ~30 km/h avg
        elapsed_time_s=int(distance_m / 7),
        elevation_gain_m=int(distance_m / 100),
        avg_speed_mps=8.0,
        avg_power_w=avg_power_w,
        title=title,
    )


# =============================================================================
# Test Basic Functionality
# =============================================================================


class TestGetMatchingActivities:
    """Tests for GetMatchingActivities use case."""

    @pytest.mark.asyncio
    async def test_returns_matching_activities(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Returns activities within distance tolerance with power data."""
        # Create matching activity (within 20% of 50km)
        activity = create_activity(user_id=1, distance_m=48000, avg_power_w=210)
        activity_repo._activities[(1, activity.id)] = activity

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 1
        assert isinstance(result[0], MatchingActivity)
        assert result[0].id == activity.id
        assert result[0].avg_power_w == 210

    @pytest.mark.asyncio
    async def test_excludes_activities_without_power(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Excludes activities without power data."""
        # Activity with power - should match
        with_power = create_activity(user_id=1, distance_m=50000, avg_power_w=220)
        activity_repo._activities[(1, with_power.id)] = with_power

        # Activity without power - should not match
        no_power = create_activity(user_id=1, distance_m=50000, avg_power_w=None)
        activity_repo._activities[(1, no_power.id)] = no_power

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 1
        assert result[0].id == with_power.id

    @pytest.mark.asyncio
    async def test_excludes_activities_with_zero_power(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Excludes activities with zero power (invalid data)."""
        # Activity with zero power
        zero_power = create_activity(user_id=1, distance_m=50000, avg_power_w=0)
        activity_repo._activities[(1, zero_power.id)] = zero_power

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_excludes_activities_too_short(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Excludes activities significantly shorter than course."""
        # Activity too short (30km vs 50km course, >20% difference)
        too_short = create_activity(user_id=1, distance_m=30000, avg_power_w=220)
        activity_repo._activities[(1, too_short.id)] = too_short

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_excludes_activities_too_long(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Excludes activities significantly longer than course."""
        # Activity too long (70km vs 50km course, >20% difference)
        too_long = create_activity(user_id=1, distance_m=70000, avg_power_w=220)
        activity_repo._activities[(1, too_long.id)] = too_long

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_includes_activities_at_tolerance_boundary(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Includes activities exactly at the tolerance boundary."""
        # 50km course with 20% tolerance = 40-60km range
        at_lower = create_activity(user_id=1, distance_m=40000, avg_power_w=220)
        at_upper = create_activity(user_id=1, distance_m=60000, avg_power_w=220)
        activity_repo._activities[(1, at_lower.id)] = at_lower
        activity_repo._activities[(1, at_upper.id)] = at_upper

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 2


class TestPlanNotFound:
    """Tests for plan not found errors."""

    @pytest.mark.asyncio
    async def test_plan_not_found_raises(
        self,
        use_case: GetMatchingActivities,
        activity_repo: FakeActivityRepo,
    ):
        """Raises ValueError when plan not found."""
        with pytest.raises(ValueError, match="Plan .* not found"):
            await use_case.execute(user_id=1, plan_id=999)

    @pytest.mark.asyncio
    async def test_wrong_user_plan_not_found(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,  # User 1's plan
        activity_repo: FakeActivityRepo,
    ):
        """Cannot access another user's plan."""
        with pytest.raises(ValueError, match="Plan .* not found"):
            await use_case.execute(user_id=2, plan_id=sample_plan.id)


class TestCourseNotFound:
    """Tests for course not found errors."""

    @pytest.mark.asyncio
    async def test_course_not_found_raises(
        self,
        plan_repo: FakeRacePlanRepo,
        activity_repo: FakeActivityRepo,
        course_repo: FakeCourseRepo,
    ):
        """Raises ValueError when course not found."""
        # Create plan pointing to non-existent course
        plan = RacePlan(
            user_id=1,
            course_id=999,  # Non-existent
            rider_weight_kg=Decimal("75.0"),
            ftp_watts=250,
            cda=Decimal("0.32"),
            crr=Decimal("0.004"),
            total_time_s=3600.0,
            total_distance_m=40000.0,
            avg_power_w=200.0,
            segment_targets=[],
        )
        saved_plan = plan_repo.add(plan)

        use_case = GetMatchingActivities(plan_repo, activity_repo, course_repo)

        with pytest.raises(ValueError, match="Course .* not found"):
            await use_case.execute(user_id=1, plan_id=saved_plan.id)


class TestDistanceTolerance:
    """Tests for custom distance tolerance."""

    @pytest.mark.asyncio
    async def test_custom_distance_tolerance(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Custom tolerance affects matching."""
        # Activity 35km (30% shorter than 50km course)
        activity = create_activity(user_id=1, distance_m=35000, avg_power_w=220)
        activity_repo._activities[(1, activity.id)] = activity

        # With default 20% tolerance - should not match
        result_20 = await use_case.execute(
            user_id=1, plan_id=sample_plan.id, distance_tolerance_pct=0.2
        )
        assert len(result_20) == 0

        # With 40% tolerance - should match
        result_40 = await use_case.execute(
            user_id=1, plan_id=sample_plan.id, distance_tolerance_pct=0.4
        )
        assert len(result_40) == 1


class TestResultLimiting:
    """Tests for result limiting."""

    @pytest.mark.asyncio
    async def test_limits_results(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Respects limit parameter."""
        # Create 10 matching activities
        for i in range(10):
            activity = create_activity(
                user_id=1,
                distance_m=50000,
                avg_power_w=200 + i,
                started_at=datetime.now() - timedelta(days=i),
            )
            activity_repo._activities[(1, activity.id)] = activity

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id, limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_default_limit(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Default limit is 20."""
        # Create 25 matching activities
        for i in range(25):
            activity = create_activity(
                user_id=1,
                distance_m=50000,
                avg_power_w=200 + i,
            )
            activity_repo._activities[(1, activity.id)] = activity

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 20


class TestReturnedData:
    """Tests for returned MatchingActivity data."""

    @pytest.mark.asyncio
    async def test_returns_correct_fields(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Returns all expected fields in MatchingActivity."""
        started_at = datetime(2024, 6, 15, 10, 30, 0)
        activity = create_activity(
            user_id=1,
            distance_m=50000,
            avg_power_w=235,
            started_at=started_at,
            title="Morning Ride",
        )
        activity_repo._activities[(1, activity.id)] = activity

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 1
        match = result[0]
        assert match.id == activity.id
        assert match.title == "Morning Ride"
        assert match.started_at == started_at
        assert match.total_distance_m == 50000
        assert match.avg_power_w == 235
        assert match.moving_time_s > 0

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_matches(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Returns empty list when no activities match."""
        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)
        assert result == []


class TestEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_activity_with_none_distance(
        self,
        use_case: GetMatchingActivities,
        sample_plan: RacePlan,
        sample_course: RaceCourse,
        activity_repo: FakeActivityRepo,
    ):
        """Activities with None distance are excluded."""
        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
            total_distance_m=None,  # No distance
            moving_time_s=3600,
            elapsed_time_s=3700,
            avg_power_w=220,
        )
        activity_repo._activities[(1, activity.id)] = activity

        result = await use_case.execute(user_id=1, plan_id=sample_plan.id)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_very_short_course(
        self,
        plan_repo: FakeRacePlanRepo,
        activity_repo: FakeActivityRepo,
        course_repo: FakeCourseRepo,
    ):
        """Works with very short courses."""
        # 5km course
        short_course = RaceCourse(
            user_id=1,
            name="Short Course",
            source_type="gpx",
            distance_m=5000,
            elevation_gain_m=50,
            elevation_loss_m=50,
            geometry="LINESTRING(0 0, 1 1)",
            segments=[],
        )
        saved_course = course_repo.add(short_course)

        plan = RacePlan(
            user_id=1,
            course_id=saved_course.id,
            rider_weight_kg=Decimal("75.0"),
            ftp_watts=250,
            cda=Decimal("0.32"),
            crr=Decimal("0.004"),
            total_time_s=600.0,
            total_distance_m=5000.0,
            avg_power_w=200.0,
            segment_targets=[],
        )
        saved_plan = plan_repo.add(plan)

        # Activity matching short course
        activity = create_activity(user_id=1, distance_m=5500, avg_power_w=220)
        activity_repo._activities[(1, activity.id)] = activity

        use_case = GetMatchingActivities(plan_repo, activity_repo, course_repo)
        result = await use_case.execute(user_id=1, plan_id=saved_plan.id)

        assert len(result) == 1
