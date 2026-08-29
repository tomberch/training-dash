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
        # Warning about using defaults (from aero_selection)
        assert any("default" in w.lower() for w in result.warnings)
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


class TestGenerateRacePlanPersonalizedCoefficients:
    """Tests for personalized pacing coefficients."""

    @pytest.fixture
    def pacing_coefficients_repo(self):
        from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
        from trainingdash.domain.pacing_model import PacingCoefficients

        repo = FakePacingCoefficientsRepo()
        # Add user default coefficients
        repo.add(
            PacingCoefficients(
                user_id=1,
                bike_id=None,  # User default
                grade_power_intercept=1.15,  # Higher than default 1.10
                grade_power_slope=0.045,  # Higher than default 0.035
                max_descent_speed_mps=16.0,  # Lower than default 18.0
                descent_power_multiplier=0.40,
                curvature_speed_coefficient=-70.0,
                climb_sample_count=5000,
                descent_sample_count=3000,
                activity_count=25,
            )
        )
        # Add bike-specific coefficients for bike 1
        repo.add(
            PacingCoefficients(
                user_id=1,
                bike_id=1,
                grade_power_intercept=1.08,  # Different from user default
                grade_power_slope=0.030,
                max_descent_speed_mps=20.0,  # Faster descent
                descent_power_multiplier=0.55,
                curvature_speed_coefficient=-60.0,
                climb_sample_count=2000,
                descent_sample_count=1500,
                activity_count=10,
            )
        )
        return repo

    @pytest.fixture
    def use_case_with_coefficients(self, course_repo, bike_repo, user_repo, plan_repo, pacing_coefficients_repo):
        return GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo, pacing_coefficients_repo)

    @pytest.mark.asyncio
    async def test_uses_user_default_coefficients_when_no_bike(self, use_case_with_coefficients):
        """Uses user default coefficients when no bike specified."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=None,  # No bike = user default
            ftp_watts=250,
        )

        result = await use_case_with_coefficients.execute(user_id=1, request=request)

        # Plan should be generated successfully
        assert result.plan is not None
        assert result.plan.total_time_s > 0

    @pytest.mark.asyncio
    async def test_uses_bike_specific_coefficients(self, use_case_with_coefficients):
        """Uses bike-specific coefficients when bike specified."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,  # Has specific coefficients
            ftp_watts=250,
        )

        result = await use_case_with_coefficients.execute(user_id=1, request=request)

        # Plan should be generated successfully
        assert result.plan is not None
        assert result.plan.total_time_s > 0

    @pytest.mark.asyncio
    async def test_falls_back_to_user_default_for_unknown_bike(self, use_case_with_coefficients):
        """Falls back to user default when bike has no specific coefficients."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=999,  # Non-existent bike
            ftp_watts=250,
        )

        result = await use_case_with_coefficients.execute(user_id=1, request=request)

        # Plan should still be generated using fallback
        assert result.plan is not None
        assert any("not found" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_works_without_coefficients_repo(self, use_case):
        """Works when no coefficients repo is provided (uses global defaults)."""
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=250,
        )

        # use_case fixture doesn't have coefficients repo
        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert result.plan.total_time_s > 0


class TestGenerateRacePlanWind:
    """Wind-aware plan generation via overrides (no network)."""

    @pytest.fixture
    def course_with_bearings(self, course_repo):
        """Course whose segments all carry bearings (headwind + tailwind)."""
        course = course_repo._courses[(1, 1)]
        course.segments = [
            {
                "start_m": 0,
                "end_m": 5000,
                "distance_m": 5000,
                "avg_grade_pct": 0.0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "terrain_type": "flat",
                "bearing_deg": 0,  # north
            },
            {
                "start_m": 5000,
                "end_m": 10000,
                "distance_m": 5000,
                "avg_grade_pct": 0.0,
                "elevation_gain_m": 0,
                "elevation_loss_m": 0,
                "terrain_type": "flat",
                "bearing_deg": 180,  # south
            },
        ]
        return course_repo

    @pytest.mark.asyncio
    async def test_wind_override_generates_plan_without_crashing(
        self, course_with_bearings, bike_repo, user_repo, plan_repo
    ):
        """Wind > 0.1 m/s over bearing-bearing segments must not crash.

        Regression: GenerateRacePlan built EnvironmentParams(headwind_mps=...)
        but EnvironmentParams' field is wind_speed_mps — TypeError for any
        windy plan over segments with bearings.
        """
        use_case = GenerateRacePlan(course_with_bearings, bike_repo, user_repo, plan_repo)
        request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            target_intensity=0.85,
            wind_override_speed_mps=5.0,
            wind_override_direction_deg=0,  # from north
        )

        result = await use_case.execute(user_id=1, request=request)

        assert result.plan is not None
        assert result.plan.total_time_s > 0
        assert any("wind override" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_wind_changes_plan_times(self, course_with_bearings, bike_repo, user_repo, plan_repo):
        """Headwind on leg 1 and tailwind on leg 2 must affect segment times.

        With per-segment headwind applied, the northbound leg (full headwind)
        takes longer and the southbound leg (full tailwind) is faster than
        the calm-condition plan. A uniform-env plan gives identical times.
        """
        calm = GenerateRacePlan(course_with_bearings, bike_repo, user_repo, plan_repo)
        calm_request = GeneratePlanRequest(course_id=1, bike_id=1, ftp_watts=280)
        calm_result = await calm.execute(user_id=1, request=calm_request)

        windy = GenerateRacePlan(course_with_bearings, bike_repo, user_repo, plan_repo)
        windy_request = GeneratePlanRequest(
            course_id=1,
            bike_id=1,
            ftp_watts=280,
            wind_override_speed_mps=5.0,
            wind_override_direction_deg=0,  # from north
        )
        windy_result = await windy.execute(user_id=1, request=windy_request)

        calm_targets = calm_result.plan.segment_targets
        windy_targets = windy_result.plan.segment_targets
        assert len(windy_targets) == len(calm_targets) == 2

        # Leg 1 (north, full headwind): slower than calm
        assert windy_targets[0]["time_s"] > calm_targets[0]["time_s"]
        # Leg 2 (south, full tailwind): faster than calm
        assert windy_targets[1]["time_s"] < calm_targets[1]["time_s"]


class TestPlanTypeModulation:
    """#636: same course, two ride types → different plans, direction pinned."""

    @pytest.fixture
    def hilly_course_repo(self):
        """Course with a real descent (< -3%) so the Descent Multiplier applies."""
        repo = FakeCourseRepo()
        profile = []
        # 1km flat, 2km climb at 5%, 2km descent at -5%
        for i in range(101):
            d = i * 50.0
            elev = 100.0 + max(0.0, min(d, 3000.0) - 1000.0) * 0.05 - max(0.0, d - 3000.0) * 0.05
            profile.append({"distance_m": d, "elevation_m": elev, "grade_pct": 0.0, "lat": 47.0, "lon": 8.0})
        course = RaceCourse(
            id=1,
            user_id=1,
            name="Hilly",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=100.0,
            geometry="SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)",
            segments=[
                {
                    "start_m": 0,
                    "end_m": 1000,
                    "distance_m": 1000,
                    "avg_grade_pct": 0.0,
                    "elevation_gain_m": 0,
                    "elevation_loss_m": 0,
                    "terrain_type": "flat",
                },
                {
                    "start_m": 1000,
                    "end_m": 3000,
                    "distance_m": 2000,
                    "avg_grade_pct": 5.0,
                    "elevation_gain_m": 100,
                    "elevation_loss_m": 0,
                    "terrain_type": "climb",
                },
                {
                    "start_m": 3000,
                    "end_m": 5000,
                    "distance_m": 2000,
                    "avg_grade_pct": -5.0,
                    "elevation_gain_m": 0,
                    "elevation_loss_m": 100,
                    "terrain_type": "descent",
                },
            ],
            elevation_profile=profile,
        )
        repo.add(course)
        return repo

    @pytest.fixture
    def calibrated_pacing_repo(self):
        from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
        from trainingdash.domain.pacing_model import PacingCoefficients

        repo = FakePacingCoefficientsRepo()
        repo.add(
            PacingCoefficients(
                user_id=1,
                bike_id=None,
                descent_power_multiplier=0.12,  # learned near-coaster
                activity_count=10,
            )
        )
        return repo

    def _use_case(self, course_repo, pacing_repo, bike_repo, user_repo, plan_repo):
        return GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo, pacing_repo)

    @pytest.mark.asyncio
    async def test_race_vs_touring_descends_differently(
        self, hilly_course_repo, calibrated_pacing_repo, bike_repo, user_repo, plan_repo
    ):
        """Race pedals descents harder than touring; stop time differs;
        both traceable to the same learned baseline via the comparison dict."""
        uc = self._use_case(hilly_course_repo, calibrated_pacing_repo, bike_repo, user_repo, plan_repo)

        race = await uc.execute(
            user_id=1,
            request=GeneratePlanRequest(course_id=1, ftp_watts=250, ride_type="race", name="race-plan"),
        )
        touring = await uc.execute(
            user_id=1,
            request=GeneratePlanRequest(course_id=1, ftp_watts=250, ride_type="touring", name="touring-plan"),
        )

        # Same learned baseline for both
        assert race.comparison["learned_descent_power_multiplier"] == pytest.approx(0.12)
        assert touring.comparison["learned_descent_power_multiplier"] == pytest.approx(0.12)
        # Different modulated values, direction pinned
        race_mod = race.comparison["modulated_descent_power_multiplier"]
        touring_mod = touring.comparison["modulated_descent_power_multiplier"]
        assert touring_mod < race_mod
        # Stop time: race < touring
        assert race.plan.total_time_s < touring.plan.total_time_s
        # Descent segment targets: race pedals harder
        race_descent = [t for t in race.plan.segment_targets if t["segment_idx"] == 2]
        touring_descent = [t for t in touring.plan.segment_targets if t["segment_idx"] == 2]
        assert race_descent[0]["power_w"] > touring_descent[0]["power_w"]

    @pytest.mark.asyncio
    async def test_training_ride_type_is_identity(
        self, hilly_course_repo, calibrated_pacing_repo, bike_repo, user_repo, plan_repo
    ):
        """Training plan's modulated value = learned baseline exactly."""
        uc = self._use_case(hilly_course_repo, calibrated_pacing_repo, bike_repo, user_repo, plan_repo)

        training = await uc.execute(
            user_id=1,
            request=GeneratePlanRequest(course_id=1, ftp_watts=250, ride_type="training"),
        )

        assert training.comparison["modulated_descent_power_multiplier"] == pytest.approx(0.12)


class TestTargetTimeMode:
    """#637: target-time requests hit the scaled terrain-shaped engine."""

    @pytest.fixture
    def hilly_course_repo(self):
        repo = FakeCourseRepo()
        profile = []
        for i in range(121):
            d = i * 50.0
            if d <= 2000:
                grade, elev = 0.0, 100.0
            elif d <= 4000:
                grade, elev = 5.0, 100.0 + (d - 2000) * 0.05
            else:
                grade, elev = -5.0, 200.0 - (d - 4000) * 0.05
            profile.append({"distance_m": d, "elevation_m": elev, "grade_pct": grade, "lat": 47.0, "lon": 8.0})
        course = RaceCourse(
            id=1,
            user_id=1,
            name="Hilly",
            source_type="gpx",
            distance_m=6000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=100.0,
            geometry="SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)",
            segments=[
                {
                    "start_m": 0,
                    "end_m": 2000,
                    "distance_m": 2000,
                    "avg_grade_pct": 0.0,
                    "elevation_gain_m": 0,
                    "elevation_loss_m": 0,
                    "terrain_type": "flat",
                },
                {
                    "start_m": 2000,
                    "end_m": 4000,
                    "distance_m": 2000,
                    "avg_grade_pct": 5.0,
                    "elevation_gain_m": 100,
                    "elevation_loss_m": 0,
                    "terrain_type": "climb",
                },
                {
                    "start_m": 4000,
                    "end_m": 6000,
                    "distance_m": 2000,
                    "avg_grade_pct": -5.0,
                    "elevation_gain_m": 0,
                    "elevation_loss_m": 100,
                    "terrain_type": "descent",
                },
            ],
            elevation_profile=profile,
        )
        repo.add(course)
        return repo

    @pytest.fixture
    def calibrated_pacing_repo(self):
        from tests.fakes.pacing_coefficients_repo import FakePacingCoefficientsRepo
        from trainingdash.domain.pacing_model import PacingCoefficients

        repo = FakePacingCoefficientsRepo()
        repo.add(
            PacingCoefficients(
                user_id=1,
                bike_id=None,
                descent_power_multiplier=0.12,  # learned near-coaster
                activity_count=10,
            )
        )
        return repo

    @pytest.mark.asyncio
    async def test_target_time_hits_solver_and_is_terrain_shaped(
        self, hilly_course_repo, calibrated_pacing_repo, bike_repo, user_repo, plan_repo
    ):
        """target_time_s produces a terrain-shaped scaled plan: descents at
        coast level, VI > 1.0, method = 'time_scaled'."""
        uc = GenerateRacePlan(hilly_course_repo, bike_repo, user_repo, plan_repo, calibrated_pacing_repo)

        request = GeneratePlanRequest(course_id=1, ftp_watts=280, target_time_s=700.0, ride_type="training")

        result = await uc.execute(user_id=1, request=request)

        assert result.plan.optimization_method == "time_scaled"
        # Terrain-shaped: descents coasted (near-zero), not 200W+
        descent = [t for t in result.plan.segment_targets if t["segment_idx"] == 2][0]
        assert descent["power_w"] < 100
        # VI reflects variability, not the constant-power fantasy
        vi = result.plan.normalized_power_w / result.plan.avg_power_w
        assert vi > 1.02
        # Riding time honors the net target (total minus training's 6% stops)
        riding = result.comparison["riding_time_s"]
        assert riding == pytest.approx(700.0 / 1.06, rel=0.02)
        # And the achieved TOTAL time honors the request target
        assert result.plan.total_time_s == pytest.approx(700.0, rel=0.03)

    @pytest.mark.asyncio
    async def test_impossible_target_time_hard_error(self, hilly_course_repo, bike_repo, user_repo, plan_repo):
        """Faster than physically possible → ValueError with the minimum
        achievable time."""
        uc = GenerateRacePlan(hilly_course_repo, bike_repo, user_repo, plan_repo)

        with pytest.raises(ValueError, match="too fast"):
            await uc.execute(user_id=1, request=GeneratePlanRequest(course_id=1, ftp_watts=280, target_time_s=100.0))


class TestSustainability:
    """#638: every plan carries a sustainability level; red still saves."""

    @pytest.fixture
    def course_repo_for_effort(self):
        """Course long enough (2h at modest pace) for duration-adjusted IF."""
        repo = FakeCourseRepo()
        # 40km flat: ~1.5h ride
        segs = [
            {
                "start_m": 0,
                "end_m": 40000,
                "distance_m": 40000,
                "avg_grade_pct": 0.5,
                "elevation_gain_m": 200,
                "elevation_loss_m": 0,
                "terrain_type": "rolling",
            },
        ]
        profile = [{"distance_m": i * 100.0, "elevation_m": 100.0 + i * 0.5, "grade_pct": 0.5, "lat": 47.0, "lon": 8.0} for i in range(401)]
        course = RaceCourse(
            id=1,
            user_id=1,
            name="Rolling 40k",
            source_type="gpx",
            distance_m=40000.0,
            elevation_gain_m=200.0,
            elevation_loss_m=0.0,
            geometry="SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)",
            segments=segs,
            elevation_profile=profile,
        )
        repo.add(course)
        return repo

    @pytest.mark.asyncio
    async def test_easy_plan_is_green_and_saved(self, course_repo_for_effort, bike_repo, user_repo, plan_repo):
        uc = GenerateRacePlan(course_repo_for_effort, bike_repo, user_repo, plan_repo)
        result = await uc.execute(user_id=1, request=GeneratePlanRequest(course_id=1, ftp_watts=250, target_intensity=0.75))
        assert result.plan.sustainability == "green"

    @pytest.mark.asyncio
    async def test_ambitious_plan_is_yellow_or_red(self, course_repo_for_effort, bike_repo, user_repo, plan_repo):
        uc = GenerateRacePlan(course_repo_for_effort, bike_repo, user_repo, plan_repo)
        result = await uc.execute(user_id=1, request=GeneratePlanRequest(course_id=1, ftp_watts=250, target_intensity=1.05))
        assert result.plan.sustainability in ("yellow", "red")

    @pytest.mark.asyncio
    async def test_red_plan_saves_with_flag_and_warning(self, course_repo_for_effort, bike_repo, user_repo, plan_repo):
        """Red plans are saved, flagged, and carry a warning string —
        not rejected."""
        uc = GenerateRacePlan(course_repo_for_effort, bike_repo, user_repo, plan_repo)
        # Aggressive-but-possible time target on a long course: the solver
        # scales pedaling power to the ceiling → deep effort → yellow/red.
        # (3600s would be physically impossible and hard-error — that's the
        # other acceptance criterion, covered separately.)
        result = await uc.execute(
            user_id=1,
            request=GeneratePlanRequest(course_id=1, ftp_watts=250, target_time_s=4200.0),
        )
        plan = result.plan
        assert plan.id is not None, "red plan must still be saved"
        assert plan.sustainability in ("yellow", "red")
        if plan.sustainability == "red":
            assert any("very hard" in w.lower() or "beyond" in w.lower() or "red" in w.lower() for w in result.warnings)


    @pytest.mark.asyncio
    async def test_physically_impossible_time_errors_before_save(
        self, course_repo_for_effort, bike_repo, user_repo, plan_repo
    ):
        """#638: only the physically impossible is a hard error — raised
        before save, message states the minimum achievable time."""
        uc = GenerateRacePlan(course_repo_for_effort, bike_repo, user_repo, plan_repo)
        plans_before = len(plan_repo._plans) if hasattr(plan_repo, "_plans") else None

        with pytest.raises(ValueError, match=r"too fast.*[Mm]inimum achievable"):
            await uc.execute(
                user_id=1,
                request=GeneratePlanRequest(course_id=1, ftp_watts=250, target_time_s=600.0),
            )

        # Nothing was saved for the impossible request
        if plans_before is not None:
            assert len(plan_repo._plans) == plans_before
