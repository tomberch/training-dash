"""Unit tests for GenerateRacePlan use case."""

from decimal import Decimal

import pytest

from tests.fakes.bike_repo import FakeBikeRepo
from tests.fakes.course_repo import FakeCourseRepo
from tests.fakes.race_plan_repo import FakeRacePlanRepo
from tests.fakes.user_repo import FakeUserRepo
from trainingdash.repositories.postgres.models import Bike, RaceCourse, User
from trainingdash.use_cases.generate_race_plan import (
    GeneratePlanRequest,
    GenerateRacePlan,
)


@pytest.fixture
def user_repo():
    repo = FakeUserRepo()
    user = User(id=1, email="test@example.com", password_hash="x", weight_kg=Decimal("75"))
    repo._users[user.id] = user
    return repo


@pytest.fixture
def course_repo():
    repo = FakeCourseRepo()
    # Create a course with segments
    course = RaceCourse(
        id=1,
        user_id=1,
        name="Test Course",
        source_type="gpx",
        distance_m=10000.0,
        elevation_gain_m=200.0,
        elevation_loss_m=100.0,
        geometry="SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)",
        segments=[
            {
                "start_m": 0,
                "end_m": 3000,
                "distance_m": 3000,
                "avg_grade_pct": 0.0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "terrain_type": "flat",
            },
            {
                "start_m": 3000,
                "end_m": 6000,
                "distance_m": 3000,
                "avg_grade_pct": 5.0,
                "elevation_gain_m": 150,
                "elevation_loss_m": 0,
                "terrain_type": "climb",
            },
            {
                "start_m": 6000,
                "end_m": 10000,
                "distance_m": 4000,
                "avg_grade_pct": -2.5,
                "elevation_gain_m": 0,
                "elevation_loss_m": 100,
                "terrain_type": "descent",
            },
        ],
    )
    repo.add(course)
    return repo


@pytest.fixture
def bike_repo():
    repo = FakeBikeRepo()
    bike = Bike(
        id=1,
        user_id=1,
        name="Road Bike",
        bike_type="road",
        weight_kg=Decimal("8.5"),
        cda=Decimal("0.32"),
        crr=Decimal("0.004"),
        is_default=True,
    )
    repo.add(bike)
    return repo


@pytest.fixture
def plan_repo():
    return FakeRacePlanRepo()


@pytest.fixture
def use_case(course_repo, bike_repo, user_repo, plan_repo):
    return GenerateRacePlan(
        course_repo=course_repo,
        bike_repo=bike_repo,
        user_repo=user_repo,
        plan_repo=plan_repo,
    )


class TestGenerateRacePlanHappy:
    """Happy path tests for GenerateRacePlan."""

    @pytest.mark.asyncio
    async def test_generates_valid_plan(self, use_case, plan_repo):
        """Heuristic pacing generates a valid plan."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            target_intensity=0.85,
            use_optimizer=False,
            name="My Race Plan",
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert result.plan.id is not None
        assert result.plan.name == "My Race Plan"
        assert result.plan.ftp_watts == 280
        assert result.plan.total_time_s > 0
        assert result.plan.total_distance_m == 10000.0
        assert result.plan.avg_power_w > 0
        assert result.plan.segment_targets is not None
        assert len(result.plan.segment_targets) == 3

        # Plan saved to repo
        saved = plan_repo.all()
        assert len(saved) == 1

    @pytest.mark.asyncio
    async def test_generates_segment_targets(self, use_case):
        """Segment targets have required fields."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            target_intensity=0.85,
        )

        result = await use_case.execute(user_id=1, request=request)

        for target in result.plan.segment_targets:
            assert "segment_idx" in target
            assert "power_w" in target
            assert "time_s" in target
            assert "speed_mps" in target
            assert target["power_w"] > 0
            assert target["time_s"] > 0
            assert target["speed_mps"] > 0

    @pytest.mark.asyncio
    async def test_comparison_includes_constant_time(self, use_case):
        """Comparison dict includes constant power baseline."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            target_intensity=0.85,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert "constant_time_s" in result.comparison
        assert "heuristic_time_s" in result.comparison
        assert "improvement_vs_constant_pct" in result.comparison
        # Heuristic should be faster than constant power
        assert result.comparison["heuristic_time_s"] <= result.comparison["constant_time_s"]


class TestGenerateRacePlanDefaults:
    """Tests for default value handling."""

    @pytest.mark.asyncio
    async def test_missing_bike_uses_defaults(self, use_case):
        """Missing bike uses road defaults with warning."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=None,  # No bike
            ftp_watts=250,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert any("No bike specified" in w for w in result.warnings)
        # Uses road defaults
        assert float(result.plan.cda) == pytest.approx(0.32, rel=0.1)
        assert float(result.plan.crr) == pytest.approx(0.004, rel=0.1)

    @pytest.mark.asyncio
    async def test_missing_bike_id_not_found(self, use_case):
        """Non-existent bike ID uses defaults with warning."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=999,  # Non-existent
            ftp_watts=250,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert any("not found" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_missing_cp_estimated_from_ftp(self, use_case):
        """Missing CP is estimated as 95% of FTP."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=300,
            cp_watts=None,  # Will be estimated
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan.cp_watts == 285  # 300 * 0.95
        assert any("CP estimated" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_missing_w_prime_uses_default(self, use_case):
        """Missing W' uses 20kJ default."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=250,
            w_prime_joules=None,  # Will use default
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan.w_prime_joules == 20000
        assert any("W'" in w and "20kJ" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_rider_weight_from_user_profile(self, use_case, user_repo):
        """Rider weight comes from user profile if not specified."""
        # Update user weight
        user_repo._users[1].weight_kg = Decimal("80")

        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=250,
            rider_weight_kg=None,  # Will use profile
        )

        result = await use_case.execute(user_id=1, request=request)

        assert float(result.plan.rider_weight_kg) == 80.0

    @pytest.mark.asyncio
    async def test_rider_weight_default_if_no_profile(self, use_case, user_repo):
        """Default 75kg used if no weight in profile."""
        user_repo._users[1].weight_kg = None

        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=250,
            rider_weight_kg=None,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert float(result.plan.rider_weight_kg) == 75.0
        assert any("75kg" in w for w in result.warnings)


class TestGenerateRacePlanErrors:
    """Error handling tests."""

    @pytest.mark.asyncio
    async def test_course_not_found_raises(self, use_case):
        """Non-existent course raises ValueError."""
        request = GeneratePlanRequest(
            course_id=999,
            ftp_watts=250,
        )

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(user_id=1, request=request)

    @pytest.mark.asyncio
    async def test_course_no_segments_raises(self, use_case, course_repo):
        """Course with no segments raises ValueError."""
        # Create course without segments
        empty_course = RaceCourse(
            id=2,
            user_id=1,
            name="Empty Course",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            geometry="SRID=4326;LINESTRINGZ(0 0 100, 1 1 100)",
            segments=[],  # Empty
        )
        course_repo.add(empty_course)

        request = GeneratePlanRequest(
            course_id=2,
            ftp_watts=250,
        )

        with pytest.raises(ValueError, match="no segments"):
            await use_case.execute(user_id=1, request=request)


class TestGenerateRacePlanOptimizer:
    """Tests for optimizer mode."""

    @pytest.mark.asyncio
    async def test_optimizer_produces_plan(self, use_case):
        """Optimizer mode produces a valid plan."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            cp_watts=270,
            w_prime_joules=20000,
            target_intensity=0.85,
            use_optimizer=True,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert result.plan.optimization_method == "optimized"
        assert result.plan.total_time_s > 0
        assert len(result.plan.segment_targets) == 3

    @pytest.mark.asyncio
    async def test_optimizer_comparison_includes_improvement(self, use_case):
        """Optimizer comparison includes improvement percentages."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            cp_watts=270,
            w_prime_joules=20000,
            use_optimizer=True,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert "optimized_time_s" in result.comparison
        assert "improvement_vs_heuristic_pct" in result.comparison
        assert "improvement_vs_constant_pct" in result.comparison


class TestGenerateRacePlanWbal:
    """Tests for W'bal tracking."""

    @pytest.mark.asyncio
    async def test_wbal_min_calculated(self, use_case):
        """W'bal minimum is calculated and saved."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            cp_watts=270,
            w_prime_joules=20000,
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan.wbal_min is not None
        assert result.plan.wbal_min >= 0
        assert result.plan.wbal_min <= 20000
