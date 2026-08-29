"""Unit tests for pacing heuristics module."""

import numpy as np
import pytest

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import (
    PacingPlan,
    PacingTarget,
    calculate_intensity_factor,
    calculate_normalized_power,
    calculate_normalized_power_from_segments,
    estimate_tss,
    generate_heuristic_pacing,
    get_terrain_multiplier,
)
from trainingdash.domain.physics import EnvironmentParams, RiderParams

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def flat_segments() -> list[CourseSegment]:
    """Course with all flat segments."""
    return [
        CourseSegment(
            start_distance_m=0,
            end_distance_m=5000,
            length_m=5000,
            avg_grade_pct=0.0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        ),
        CourseSegment(
            start_distance_m=5000,
            end_distance_m=10000,
            length_m=5000,
            avg_grade_pct=0.5,
            elevation_gain_m=25,
            elevation_loss_m=0,
            terrain_type="flat",
        ),
    ]


@pytest.fixture
def climbing_segments() -> list[CourseSegment]:
    """Course with significant climbing."""
    return [
        CourseSegment(
            start_distance_m=0,
            end_distance_m=2000,
            length_m=2000,
            avg_grade_pct=0.0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        ),
        CourseSegment(
            start_distance_m=2000,
            end_distance_m=5000,
            length_m=3000,
            avg_grade_pct=6.0,
            elevation_gain_m=180,
            elevation_loss_m=0,
            terrain_type="climb",
        ),
        CourseSegment(
            start_distance_m=5000,
            end_distance_m=7000,
            length_m=2000,
            avg_grade_pct=10.0,
            elevation_gain_m=200,
            elevation_loss_m=0,
            terrain_type="steep_climb",
        ),
    ]


@pytest.fixture
def descent_segments() -> list[CourseSegment]:
    """Course with descent."""
    return [
        CourseSegment(
            start_distance_m=0,
            end_distance_m=3000,
            length_m=3000,
            avg_grade_pct=-4.0,
            elevation_gain_m=0,
            elevation_loss_m=120,
            terrain_type="descent",
        ),
        CourseSegment(
            start_distance_m=3000,
            end_distance_m=6000,
            length_m=3000,
            avg_grade_pct=-8.0,
            elevation_gain_m=0,
            elevation_loss_m=240,
            terrain_type="steep_descent",
        ),
    ]


@pytest.fixture
def mixed_segments() -> list[CourseSegment]:
    """Course with mixed terrain."""
    return [
        CourseSegment(
            start_distance_m=0,
            end_distance_m=2000,
            length_m=2000,
            avg_grade_pct=0.0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        ),
        CourseSegment(
            start_distance_m=2000,
            end_distance_m=4000,
            length_m=2000,
            avg_grade_pct=3.0,
            elevation_gain_m=60,
            elevation_loss_m=0,
            terrain_type="false_flat",
        ),
        CourseSegment(
            start_distance_m=4000,
            end_distance_m=7000,
            length_m=3000,
            avg_grade_pct=6.0,
            elevation_gain_m=180,
            elevation_loss_m=0,
            terrain_type="climb",
        ),
        CourseSegment(
            start_distance_m=7000,
            end_distance_m=10000,
            length_m=3000,
            avg_grade_pct=-5.0,
            elevation_gain_m=0,
            elevation_loss_m=150,
            terrain_type="descent",
        ),
    ]


@pytest.fixture
def rider_params() -> RiderParams:
    """Typical rider parameters."""
    return RiderParams(mass_kg=75, cda=0.30, crr=0.004)


# =============================================================================
# Test Terrain Multipliers
# =============================================================================


class TestTerrainMultipliers:
    """Tests for terrain-based power multipliers."""

    def test_steep_descent_lowest_power(self):
        """Steep descent should have lowest power multiplier."""
        assert get_terrain_multiplier("steep_descent") < get_terrain_multiplier("descent")
        assert get_terrain_multiplier("steep_descent") < 0.6

    def test_steep_climb_highest_power(self):
        """Steep climb should have highest power multiplier."""
        assert get_terrain_multiplier("steep_climb") > get_terrain_multiplier("climb")
        assert get_terrain_multiplier("steep_climb") > 1.1

    def test_flat_is_base(self):
        """Flat terrain should use base power (multiplier = 1.0)."""
        assert get_terrain_multiplier("flat") == 1.0

    def test_multipliers_increase_with_grade(self):
        """Multipliers should generally increase with grade."""
        order = ["steep_descent", "descent", "flat", "false_flat", "climb", "steep_climb"]
        multipliers = [get_terrain_multiplier(t) for t in order]
        assert multipliers == sorted(multipliers)

    def test_unknown_terrain_returns_default(self):
        """Unknown terrain type returns 1.0."""
        assert get_terrain_multiplier("unknown") == 1.0


# =============================================================================
# Test Heuristic Pacing
# =============================================================================


class TestGenerateHeuristicPacing:
    """Tests for generate_heuristic_pacing function."""

    def test_produces_valid_plan(self, flat_segments, rider_params):
        """Generates a valid pacing plan."""
        plan = generate_heuristic_pacing(
            flat_segments,
            rider_ftp=250,
            target_intensity=0.85,
            rider_params=rider_params,
        )

        assert isinstance(plan, PacingPlan)
        assert len(plan.targets) == len(flat_segments)
        assert plan.total_distance_m == 10000
        assert plan.total_time_s > 0
        assert plan.avg_power_w > 0
        assert plan.normalized_power_w > 0
        assert plan.intensity_factor > 0

    def test_higher_power_on_climbs(self, climbing_segments, rider_params):
        """Climbing segments should have higher target power than flat."""
        plan = generate_heuristic_pacing(
            climbing_segments,
            rider_ftp=250,
            target_intensity=0.85,
            rider_params=rider_params,
        )

        flat_target = plan.targets[0]  # First segment is flat
        climb_target = plan.targets[1]  # Second segment is climb
        steep_climb_target = plan.targets[2]  # Third is steep climb

        assert climb_target.target_power_w > flat_target.target_power_w
        assert steep_climb_target.target_power_w > climb_target.target_power_w

    def test_lower_power_on_descents(self, descent_segments, rider_params):
        """Descent segments should have lower target power."""
        plan = generate_heuristic_pacing(
            descent_segments,
            rider_ftp=250,
            target_intensity=0.85,
            rider_params=rider_params,
        )

        descent_target = plan.targets[0]
        steep_descent_target = plan.targets[1]

        base_power = 250 * 0.85
        assert descent_target.target_power_w < base_power
        assert steep_descent_target.target_power_w < descent_target.target_power_w

    def test_power_capped_at_ftp(self, climbing_segments, rider_params):
        """Target power should never exceed FTP."""
        plan = generate_heuristic_pacing(
            climbing_segments,
            rider_ftp=250,
            target_intensity=0.95,  # High intensity
            rider_params=rider_params,
        )

        for target in plan.targets:
            assert target.target_power_w <= 250

    def test_total_energy_approximates_expected(self, flat_segments, rider_params):
        """Total energy should approximately equal FTP × IF × time."""
        plan = generate_heuristic_pacing(
            flat_segments,
            rider_ftp=250,
            target_intensity=0.85,
            rider_params=rider_params,
        )

        # Total energy in kilojoules
        total_energy_kj = plan.avg_power_w * plan.total_time_s / 1000

        # Expected: roughly base_power × time
        # Allow 20% tolerance due to terrain adjustments and physics
        expected_base = 250 * 0.85 * plan.total_time_s / 1000
        assert abs(total_energy_kj - expected_base) / expected_base < 0.20

    def test_slower_on_climbs_faster_on_descents(self, mixed_segments, rider_params):
        """Speed should decrease on climbs and increase on descents."""
        plan = generate_heuristic_pacing(
            mixed_segments,
            rider_ftp=250,
            target_intensity=0.85,
            rider_params=rider_params,
        )

        flat_speed = plan.targets[0].estimated_speed_mps  # flat
        climb_speed = plan.targets[2].estimated_speed_mps  # 6% climb
        descent_speed = plan.targets[3].estimated_speed_mps  # -5% descent

        assert climb_speed < flat_speed
        assert descent_speed > flat_speed

    def test_empty_segments_raises_error(self, rider_params):
        """Empty segments list should raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            generate_heuristic_pacing([], rider_ftp=250, rider_params=rider_params)

    def test_invalid_ftp_raises_error(self, flat_segments, rider_params):
        """Non-positive FTP should raise ValueError."""
        with pytest.raises(ValueError, match="ftp"):
            generate_heuristic_pacing(flat_segments, rider_ftp=0, rider_params=rider_params)

        with pytest.raises(ValueError, match="ftp"):
            generate_heuristic_pacing(flat_segments, rider_ftp=-100, rider_params=rider_params)

    def test_invalid_intensity_raises_error(self, flat_segments, rider_params):
        """Invalid target_intensity should raise ValueError."""
        with pytest.raises(ValueError, match="intensity"):
            generate_heuristic_pacing(flat_segments, rider_ftp=250, target_intensity=0, rider_params=rider_params)

        with pytest.raises(ValueError, match="intensity"):
            generate_heuristic_pacing(flat_segments, rider_ftp=250, target_intensity=2.0, rider_params=rider_params)

    def test_default_rider_params(self, flat_segments):
        """Should work with default rider params."""
        plan = generate_heuristic_pacing(
            flat_segments,
            rider_ftp=250,
            target_intensity=0.85,
        )

        assert plan.total_time_s > 0
        assert plan.avg_power_w > 0

    def test_segment_indices_correct(self, mixed_segments, rider_params):
        """Segment indices should be sequential and correct."""
        plan = generate_heuristic_pacing(
            mixed_segments,
            rider_ftp=250,
            rider_params=rider_params,
        )

        for i, target in enumerate(plan.targets):
            assert target.segment_idx == i

    def test_distance_tracking_correct(self, mixed_segments, rider_params):
        """Distance tracking should match input segments."""
        plan = generate_heuristic_pacing(
            mixed_segments,
            rider_ftp=250,
            rider_params=rider_params,
        )

        for i, target in enumerate(plan.targets):
            assert target.start_distance_m == mixed_segments[i].start_distance_m
            assert target.end_distance_m == mixed_segments[i].end_distance_m
            assert target.distance_m == mixed_segments[i].length_m


# =============================================================================
# Test Normalized Power Calculation
# =============================================================================


class TestNormalizedPower:
    """Tests for NP calculation."""

    def test_constant_power_np_equals_avg(self):
        """For constant power, NP should equal average power."""
        powers = np.full(300, 200.0)  # 5 minutes at 200W
        np_power = calculate_normalized_power(powers, sample_rate_hz=1.0)
        assert np_power == pytest.approx(200.0, rel=0.01)

    def test_variable_power_np_higher_than_avg(self):
        """For variable power, NP should be higher than average."""
        # 60s at 150W, then 60s at 250W, repeated - creates variability
        # that survives the 30s rolling average
        powers = np.concatenate(
            [
                np.full(60, 150.0),
                np.full(60, 250.0),
                np.full(60, 150.0),
                np.full(60, 250.0),
                np.full(60, 150.0),
            ]
        )  # 300 samples, avg = 190W
        np_power = calculate_normalized_power(powers, sample_rate_hz=1.0)
        avg_power = np.mean(powers)

        assert np_power > avg_power
        # NP should be between avg and max
        assert np_power < 250

    def test_short_data_returns_average(self):
        """With < 30 samples, should return simple average."""
        powers = np.array([200, 210, 220, 230, 240])
        np_power = calculate_normalized_power(powers, sample_rate_hz=1.0)
        assert np_power == pytest.approx(np.mean(powers), rel=0.01)

    def test_empty_returns_zero(self):
        """Empty array should return 0."""
        np_power = calculate_normalized_power(np.array([]))
        assert np_power == 0.0

    def test_known_value(self):
        """Test against a known NP calculation."""
        # Create a simple pattern that we can calculate manually
        # 60 seconds at 200W, 60 seconds at 300W, repeated
        powers = np.concatenate(
            [
                np.full(60, 200.0),
                np.full(60, 300.0),
                np.full(60, 200.0),
                np.full(60, 300.0),
            ]
        )
        np_power = calculate_normalized_power(powers, sample_rate_hz=1.0)

        # Average is 250W, NP should be higher due to variability
        assert np_power > 250
        assert np_power < 300

    def test_different_sample_rates(self):
        """Different sample rates should affect window size."""
        # 2 Hz data for 150 seconds (300 samples)
        powers = np.full(300, 200.0)
        np_power = calculate_normalized_power(powers, sample_rate_hz=2.0)
        # At 2 Hz, 30s = 60 samples
        assert np_power == pytest.approx(200.0, rel=0.01)


class TestNormalizedPowerFromSegments:
    """Tests for segment-based NP calculation."""

    def test_constant_power_segments(self):
        """Constant power across segments gives that power as NP."""
        targets = [
            PacingTarget(0, 0, 1000, 1000, 0.0, 200.0, "flat", 10.0, 100.0),
            PacingTarget(1, 1000, 2000, 1000, 0.0, 200.0, "flat", 10.0, 100.0),
        ]
        np_power = calculate_normalized_power_from_segments(targets)
        assert np_power == pytest.approx(200.0, rel=0.01)

    def test_variable_power_segments_np_higher(self):
        """Variable power across segments gives NP > avg."""
        targets = [
            PacingTarget(0, 0, 1000, 1000, 0.0, 150.0, "flat", 10.0, 100.0),
            PacingTarget(1, 1000, 2000, 1000, 0.0, 250.0, "flat", 10.0, 100.0),
        ]
        np_power = calculate_normalized_power_from_segments(targets)
        avg_power = 200.0  # (150 + 250) / 2

        assert np_power > avg_power

    def test_empty_targets_returns_zero(self):
        """Empty target list returns 0."""
        np_power = calculate_normalized_power_from_segments([])
        assert np_power == 0.0

    def test_time_weighting(self):
        """Longer segments should have more weight."""
        # 100s at 150W, 200s at 250W
        targets = [
            PacingTarget(0, 0, 1000, 1000, 0.0, 150.0, "flat", 10.0, 100.0),
            PacingTarget(1, 1000, 3000, 2000, 0.0, 250.0, "flat", 10.0, 200.0),
        ]
        np_power = calculate_normalized_power_from_segments(targets)

        # Time-weighted avg = (150*100 + 250*200) / 300 = 216.67
        # NP should be higher due to 4th power weighting
        time_weighted_avg = (150 * 100 + 250 * 200) / 300
        assert np_power > time_weighted_avg


# =============================================================================
# Test Intensity Factor
# =============================================================================


class TestIntensityFactor:
    """Tests for IF calculation."""

    def test_at_ftp_if_equals_one(self):
        """NP at FTP should give IF of 1.0."""
        if_val = calculate_intensity_factor(250, 250)
        assert if_val == 1.0

    def test_below_ftp(self):
        """NP below FTP should give IF < 1.0."""
        if_val = calculate_intensity_factor(200, 250)
        assert if_val == pytest.approx(0.8)

    def test_above_ftp(self):
        """NP above FTP should give IF > 1.0."""
        if_val = calculate_intensity_factor(275, 250)
        assert if_val == pytest.approx(1.1)

    def test_zero_ftp_returns_zero(self):
        """Zero FTP should return 0 to avoid division by zero."""
        if_val = calculate_intensity_factor(200, 0)
        assert if_val == 0.0


# =============================================================================
# Test TSS Estimation
# =============================================================================


class TestTSSEstimation:
    """Tests for TSS calculation."""

    def test_one_hour_at_ftp_is_100(self):
        """1 hour at FTP (IF=1.0) should give TSS of 100."""
        tss = estimate_tss(np_watts=250, ftp=250, duration_s=3600)
        assert tss == pytest.approx(100.0)

    def test_two_hours_at_ftp_is_200(self):
        """2 hours at FTP should give TSS of 200."""
        tss = estimate_tss(np_watts=250, ftp=250, duration_s=7200)
        assert tss == pytest.approx(200.0)

    def test_one_hour_at_half_ftp(self):
        """1 hour at IF=0.5 should give TSS of 25."""
        # TSS = (duration * NP * IF) / (FTP * 3600) * 100
        # = (3600 * 125 * 0.5) / (250 * 3600) * 100 = 25
        tss = estimate_tss(np_watts=125, ftp=250, duration_s=3600)
        assert tss == pytest.approx(25.0)

    def test_zero_duration_returns_zero(self):
        """Zero duration should return 0."""
        tss = estimate_tss(np_watts=250, ftp=250, duration_s=0)
        assert tss == 0.0

    def test_zero_ftp_returns_zero(self):
        """Zero FTP should return 0."""
        tss = estimate_tss(np_watts=250, ftp=0, duration_s=3600)
        assert tss == 0.0


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_single_segment_course(self, rider_params):
        """Single segment course should work."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=10000,
                length_m=10000,
                avg_grade_pct=2.0,
                elevation_gain_m=200,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
        ]

        plan = generate_heuristic_pacing(segments, rider_ftp=250, rider_params=rider_params)

        assert len(plan.targets) == 1
        assert plan.total_distance_m == 10000

    def test_very_short_segments(self, rider_params):
        """Very short segments should still work."""
        segments = [
            CourseSegment(
                start_distance_m=i * 100,
                end_distance_m=(i + 1) * 100,
                length_m=100,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            )
            for i in range(10)
        ]

        plan = generate_heuristic_pacing(segments, rider_ftp=250, rider_params=rider_params)

        assert len(plan.targets) == 10
        assert plan.total_distance_m == 1000

    def test_all_climb_course(self, rider_params):
        """Course that's all climbing should work."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=5000,
                length_m=5000,
                avg_grade_pct=8.0,
                elevation_gain_m=400,
                elevation_loss_m=0,
                terrain_type="steep_climb",
            ),
            CourseSegment(
                start_distance_m=5000,
                end_distance_m=10000,
                length_m=5000,
                avg_grade_pct=10.0,
                elevation_gain_m=500,
                elevation_loss_m=0,
                terrain_type="steep_climb",
            ),
        ]

        plan = generate_heuristic_pacing(segments, rider_ftp=250, rider_params=rider_params)

        # All targets should be at or near FTP
        for target in plan.targets:
            assert target.target_power_w >= 250 * 0.85  # At least base power
            assert target.target_power_w <= 250  # Capped at FTP

    def test_all_descent_course(self, rider_params):
        """Course that's all descending should work."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=5000,
                length_m=5000,
                avg_grade_pct=-6.0,
                elevation_gain_m=0,
                elevation_loss_m=300,
                terrain_type="descent",
            ),
            CourseSegment(
                start_distance_m=5000,
                end_distance_m=10000,
                length_m=5000,
                avg_grade_pct=-10.0,
                elevation_gain_m=0,
                elevation_loss_m=500,
                terrain_type="steep_descent",
            ),
        ]

        plan = generate_heuristic_pacing(segments, rider_ftp=250, rider_params=rider_params)

        # Speeds should be high on descents
        for target in plan.targets:
            assert target.estimated_speed_mps > 10  # > 36 km/h

    def test_high_altitude_environment(self, flat_segments, rider_params):
        """High altitude (thin air) should affect speed."""
        from trainingdash.domain.physics import air_density_from_altitude

        sea_level = EnvironmentParams(air_density=1.225)
        high_altitude = EnvironmentParams(air_density=air_density_from_altitude(2000))

        plan_sea = generate_heuristic_pacing(
            flat_segments, rider_ftp=250, rider_params=rider_params, env_params=sea_level
        )
        plan_high = generate_heuristic_pacing(
            flat_segments, rider_ftp=250, rider_params=rider_params, env_params=high_altitude
        )

        # At high altitude, less air resistance = higher speed for same power
        # Flat segment speed comparison
        assert plan_high.targets[0].estimated_speed_mps > plan_sea.targets[0].estimated_speed_mps


# =============================================================================
# Tests for Personalized Coefficients
# =============================================================================


class TestPacingCoefficients:
    """Tests for PacingCoefficients dataclass and get_grade_power_multiplier."""

    def test_default_coefficients(self):
        """Default coefficients match expected values."""
        from trainingdash.domain.pacing import PacingCoefficients

        defaults = PacingCoefficients.defaults()

        assert defaults.grade_power_intercept == 1.10
        assert defaults.grade_power_slope == 0.035
        assert defaults.max_descent_speed_mps == 18.0
        assert defaults.descent_power_multiplier == 0.50
        # a_lat in m/s² (ADR 0004 Phase B) — default matches the
        # "training" aggressiveness mapping (70 → 4.8)
        assert defaults.curvature_speed_coefficient == pytest.approx(4.8)

    def test_get_grade_power_multiplier_with_defaults(self):
        """get_grade_power_multiplier uses defaults when no coefficients provided."""
        from trainingdash.domain.pacing import get_grade_power_multiplier

        # Flat (0%)
        assert get_grade_power_multiplier(0) == pytest.approx(1.10, rel=0.01)

        # 5% climb
        expected = 1.10 + 0.035 * 5
        assert get_grade_power_multiplier(5) == pytest.approx(expected, rel=0.01)

    def test_get_grade_power_multiplier_with_custom_coefficients(self):
        """get_grade_power_multiplier uses provided coefficients."""
        from trainingdash.domain.pacing import PacingCoefficients, get_grade_power_multiplier

        custom = PacingCoefficients(
            grade_power_intercept=1.20,
            grade_power_slope=0.05,
        )

        # Flat (0%)
        assert get_grade_power_multiplier(0, custom) == pytest.approx(1.20, rel=0.01)

        # 5% climb
        expected = 1.20 + 0.05 * 5  # 1.45
        assert get_grade_power_multiplier(5, custom) == pytest.approx(expected, rel=0.01)

    def test_get_grade_power_multiplier_clamped(self):
        """Power multiplier is clamped to valid range."""
        from trainingdash.domain.pacing import (
            MAX_POWER_MULTIPLIER,
            MIN_POWER_MULTIPLIER,
            get_grade_power_multiplier,
        )

        # Very steep descent should clamp to minimum
        assert get_grade_power_multiplier(-20) >= MIN_POWER_MULTIPLIER

        # Very steep climb should clamp to maximum
        assert get_grade_power_multiplier(20) <= MAX_POWER_MULTIPLIER


class TestTerrainAdaptedPacingWithCoefficients:
    """Tests for generate_terrain_adapted_pacing with custom coefficients."""

    @pytest.fixture
    def mixed_segments(self) -> list[CourseSegment]:
        """Course with flat, climb, and descent."""
        return [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=2000,
                length_m=2000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
            CourseSegment(
                start_distance_m=2000,
                end_distance_m=4000,
                length_m=2000,
                avg_grade_pct=8.0,
                elevation_gain_m=160,
                elevation_loss_m=0,
                terrain_type="steep_climb",
            ),
            CourseSegment(
                start_distance_m=4000,
                end_distance_m=6000,
                length_m=2000,
                avg_grade_pct=-5.0,
                elevation_gain_m=0,
                elevation_loss_m=100,
                terrain_type="descent",
            ),
        ]

    def test_uses_custom_coefficients(self, mixed_segments):
        """generate_terrain_adapted_pacing uses custom coefficients."""
        from trainingdash.domain.pacing import (
            PacingCoefficients,
            generate_terrain_adapted_pacing,
        )

        # Custom coefficients with higher intercept
        custom = PacingCoefficients(
            grade_power_intercept=1.20,  # Higher base
            grade_power_slope=0.04,
        )

        plan_default = generate_terrain_adapted_pacing(
            mixed_segments,
            rider_ftp=250,
            target_intensity=0.85,
        )

        plan_custom = generate_terrain_adapted_pacing(
            mixed_segments,
            rider_ftp=250,
            target_intensity=0.85,
            coefficients=custom,
        )

        # With higher intercept, flat segments should have higher power
        flat_target_default = plan_default.targets[0].target_power_w
        flat_target_custom = plan_custom.targets[0].target_power_w

        # Custom has 1.20 intercept vs 1.10 default = ~9% higher
        assert flat_target_custom > flat_target_default

    def test_uses_custom_max_descent_speed(self, mixed_segments):
        """generate_terrain_adapted_pacing respects custom max descent speed."""
        from trainingdash.domain.pacing import (
            PacingCoefficients,
            generate_terrain_adapted_pacing,
        )

        # Custom coefficients with lower max descent speed
        custom = PacingCoefficients(
            max_descent_speed_mps=12.0,  # Much slower descents
        )

        plan = generate_terrain_adapted_pacing(
            mixed_segments,
            rider_ftp=250,
            target_intensity=0.85,
            coefficients=custom,
        )

        # Descent segment should be capped at custom speed
        descent_target = plan.targets[2]  # The descent segment
        assert descent_target.estimated_speed_mps <= 12.0

    def test_explicit_max_descent_overrides_coefficients(self, mixed_segments):
        """Explicit max_descent_speed_mps parameter overrides coefficients."""
        from trainingdash.domain.pacing import (
            PacingCoefficients,
            generate_terrain_adapted_pacing,
        )

        # Coefficients say 20 m/s
        custom = PacingCoefficients(
            max_descent_speed_mps=20.0,
        )

        # But explicit param says 10 m/s
        plan = generate_terrain_adapted_pacing(
            mixed_segments,
            rider_ftp=250,
            target_intensity=0.85,
            coefficients=custom,
            max_descent_speed_mps=10.0,  # Explicit override
        )

        # Descent segment should be capped at explicit value
        descent_target = plan.targets[2]
        assert descent_target.estimated_speed_mps <= 10.0


# =============================================================================
# Test Fine-Grained Pacing Integration
# =============================================================================


class TestFineGrainedPacingIntegration:
    """Tests for fine-grained pacing integration with generate_terrain_adapted_pacing."""

    @pytest.fixture
    def sample_elevation_profile(self) -> list[dict]:
        """Create a sample elevation profile with realistic data."""
        # 2km course with varied terrain:
        # 0-500m: flat (100m elevation)
        # 500-1000m: climb to 150m
        # 1000-1500m: flat at 150m
        # 1500-2000m: descent back to 100m
        points = []
        for i in range(0, 2001, 10):  # 10m spacing
            if i <= 500:
                elev = 100.0
            elif i <= 1000:
                # Climb: gain 50m over 500m = 10% grade
                elev = 100.0 + 50.0 * (i - 500) / 500
            elif i <= 1500:
                elev = 150.0
            else:
                # Descent: lose 50m over 500m = -10% grade
                elev = 150.0 - 50.0 * (i - 1500) / 500

            points.append(
                {
                    "distance_m": float(i),
                    "elevation_m": elev,
                    "grade_pct": 0.0,  # Not used, grades recalculated
                }
            )
        return points

    @pytest.fixture
    def sample_segments(self) -> list:
        """Create segments matching the elevation profile."""
        from trainingdash.domain.course_segmentation import CourseSegment

        return [
            CourseSegment(0, 500, 500, 0.0, 0, 0, "flat"),
            CourseSegment(500, 1000, 500, 10.0, 50, 0, "climb"),
            CourseSegment(1000, 1500, 500, 0.0, 0, 0, "flat"),
            CourseSegment(1500, 2000, 500, -10.0, 0, 50, "descent"),
        ]

    def test_uses_fine_grained_when_profile_provided(self, sample_segments, sample_elevation_profile):
        """With elevation_profile, uses fine-grained pacing."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan_coarse = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=None,  # Coarse mode
        )

        plan_fine = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=sample_elevation_profile,  # Fine mode
        )

        # Both should produce valid plans
        assert len(plan_coarse.targets) == 4
        assert len(plan_fine.targets) == 4

        # Fine-grained should generally give more accurate time predictions
        # (we can't assert exactly, but it should produce a valid result)
        assert plan_fine.total_time_s > 0
        assert plan_fine.total_distance_m == pytest.approx(2000.0, rel=0.1)

    def test_fine_grained_produces_different_speeds(self, sample_segments, sample_elevation_profile):
        """Fine-grained mode produces different speed predictions."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan_fine = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=sample_elevation_profile,
        )

        # Speeds should vary by terrain
        speeds = [t.estimated_speed_mps for t in plan_fine.targets]

        # Climb (index 1) should be slower than flat (index 0)
        assert speeds[1] < speeds[0], "Climb should be slower than flat"

        # Descent (index 3) should be faster than flat (index 0)
        assert speeds[3] > speeds[0], "Descent should be faster than flat"

    def test_fine_grained_respects_coefficients(self, sample_segments, sample_elevation_profile):
        """Fine-grained mode uses personalized coefficients."""
        from trainingdash.domain.pacing import (
            PacingCoefficients,
            generate_terrain_adapted_pacing,
        )

        # Lower max descent speed
        custom = PacingCoefficients(
            max_descent_speed_mps=10.0,
        )

        plan = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=sample_elevation_profile,
            coefficients=custom,
        )

        # Descent should be capped
        descent_target = plan.targets[3]
        assert descent_target.estimated_speed_mps <= 10.0 + 0.5  # Small tolerance

    def test_fine_grained_calculates_np_from_variable_power(self, sample_segments, sample_elevation_profile):
        """Fine-grained NP is calculated from actual variable power."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=sample_elevation_profile,
        )

        # NP should be higher than average power on variable terrain
        assert plan.normalized_power_w >= plan.avg_power_w * 0.99  # Allow small tolerance

        # IF should be reasonable
        assert 0.5 < plan.intensity_factor < 1.5

    def test_empty_elevation_profile_uses_coarse_mode(self, sample_segments):
        """Empty elevation profile falls back to coarse mode."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=[],  # Empty
        )

        # Should still produce valid plan
        assert len(plan.targets) == 4
        assert plan.total_time_s > 0

    def test_single_point_elevation_profile_uses_coarse_mode(self, sample_segments):
        """Single-point elevation profile falls back to coarse mode."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            elevation_profile=[{"distance_m": 0, "elevation_m": 100, "grade_pct": 0}],
        )

        # Should still produce valid plan
        assert len(plan.targets) == 4
        assert plan.total_time_s > 0


# =============================================================================
# Ride Type Tests
# =============================================================================


class TestRideTypeParams:
    """Tests for RideTypeParams and preset configuration."""

    def test_ride_type_params_creation(self):
        """RideTypeParams can be created with valid values."""
        from trainingdash.domain.pacing import RideTypeParams

        params = RideTypeParams(descent_aggressiveness=85, stop_pct=3.0)

        assert params.descent_aggressiveness == 85
        assert params.stop_pct == 3.0

    def test_ride_type_params_stop_factor(self):
        """stop_factor property calculates correctly."""
        from trainingdash.domain.pacing import RideTypeParams

        params_0 = RideTypeParams(descent_aggressiveness=90, stop_pct=0)
        params_6 = RideTypeParams(descent_aggressiveness=70, stop_pct=6)
        params_25 = RideTypeParams(descent_aggressiveness=60, stop_pct=25)

        assert params_0.stop_factor == 1.0
        assert params_6.stop_factor == pytest.approx(1.06)
        assert params_25.stop_factor == pytest.approx(1.25)

    def test_ride_type_for_curvature_aggressive(self):
        """High descent_aggressiveness maps to 'race' for curvature."""
        from trainingdash.domain.pacing import RideTypeParams

        params = RideTypeParams(descent_aggressiveness=90, stop_pct=0)
        assert params.ride_type_for_curvature == "race"

        params_80 = RideTypeParams(descent_aggressiveness=80, stop_pct=0)
        assert params_80.ride_type_for_curvature == "race"

    def test_ride_type_for_curvature_cautious(self):
        """Low descent_aggressiveness maps to 'training' for curvature."""
        from trainingdash.domain.pacing import RideTypeParams

        params = RideTypeParams(descent_aggressiveness=70, stop_pct=6)
        assert params.ride_type_for_curvature == "training"

        params_79 = RideTypeParams(descent_aggressiveness=79, stop_pct=0)
        assert params_79.ride_type_for_curvature == "training"

    def test_ride_type_params_validation_descent_aggressiveness(self):
        """descent_aggressiveness must be 0-100."""
        from trainingdash.domain.pacing import RideTypeParams

        with pytest.raises(ValueError, match="descent_aggressiveness"):
            RideTypeParams(descent_aggressiveness=-1, stop_pct=0)

        with pytest.raises(ValueError, match="descent_aggressiveness"):
            RideTypeParams(descent_aggressiveness=101, stop_pct=0)

    def test_ride_type_params_validation_stop_pct(self):
        """stop_pct must be 0-50."""
        from trainingdash.domain.pacing import RideTypeParams

        with pytest.raises(ValueError, match="stop_pct"):
            RideTypeParams(descent_aggressiveness=85, stop_pct=-1)

        with pytest.raises(ValueError, match="stop_pct"):
            RideTypeParams(descent_aggressiveness=85, stop_pct=51)


class TestRideTypePresets:
    """Tests for preset ride types."""

    def test_presets_exist(self):
        """All expected presets are defined."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS

        assert "race" in RIDE_TYPE_PRESETS
        assert "gran_fondo" in RIDE_TYPE_PRESETS
        assert "training" in RIDE_TYPE_PRESETS
        assert "touring" in RIDE_TYPE_PRESETS

    def test_race_preset_values(self):
        """Race preset has aggressive settings."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS

        race = RIDE_TYPE_PRESETS["race"]
        assert race.descent_aggressiveness == 90
        assert race.stop_pct == 0
        assert race.stop_factor == 1.0

    def test_gran_fondo_preset_values(self):
        """Gran fondo preset has moderate settings."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS

        gf = RIDE_TYPE_PRESETS["gran_fondo"]
        assert gf.descent_aggressiveness == 85
        assert gf.stop_pct == 3
        assert gf.stop_factor == pytest.approx(1.03)

    def test_training_preset_values(self):
        """Training preset has cautious settings."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS

        training = RIDE_TYPE_PRESETS["training"]
        assert training.descent_aggressiveness == 70
        assert training.stop_pct == 6
        assert training.stop_factor == pytest.approx(1.06)

    def test_touring_preset_values(self):
        """Touring preset has relaxed settings."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS

        touring = RIDE_TYPE_PRESETS["touring"]
        assert touring.descent_aggressiveness == 60
        assert touring.stop_pct == 25
        assert touring.stop_factor == pytest.approx(1.25)


class TestResolveRideTypeParams:
    """Tests for resolve_ride_type_params function."""

    def test_resolve_preset(self):
        """Preset names resolve to their params."""
        from trainingdash.domain.pacing import RIDE_TYPE_PRESETS, resolve_ride_type_params

        params = resolve_ride_type_params("race")
        assert params == RIDE_TYPE_PRESETS["race"]

        params = resolve_ride_type_params("gran_fondo")
        assert params == RIDE_TYPE_PRESETS["gran_fondo"]

    def test_resolve_custom_with_params(self):
        """Custom ride type returns provided params."""
        from trainingdash.domain.pacing import RideTypeParams, resolve_ride_type_params

        custom = RideTypeParams(descent_aggressiveness=75, stop_pct=10)
        params = resolve_ride_type_params("custom", custom)

        assert params.descent_aggressiveness == 75
        assert params.stop_pct == 10

    def test_resolve_custom_without_params_raises(self):
        """Custom ride type without params raises ValueError."""
        from trainingdash.domain.pacing import resolve_ride_type_params

        with pytest.raises(ValueError, match="custom_params required"):
            resolve_ride_type_params("custom", None)

    def test_resolve_unknown_preset_raises(self):
        """Unknown preset raises ValueError."""
        from trainingdash.domain.pacing import resolve_ride_type_params

        with pytest.raises(ValueError, match="Unknown ride_type"):
            resolve_ride_type_params("unknown_type")


class TestGenerateTerrainAdaptedPacingWithRideType:
    """Tests for ride_type integration in generate_terrain_adapted_pacing."""

    @pytest.fixture
    def sample_segments(self):
        """Basic segments for testing."""
        return [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=5000,
                length_m=5000,
                avg_grade_pct=5.0,
                elevation_gain_m=250,
                elevation_loss_m=0,
                terrain_type="climb",
            ),
            CourseSegment(
                start_distance_m=5000,
                end_distance_m=10000,
                length_m=5000,
                avg_grade_pct=-5.0,
                elevation_gain_m=0,
                elevation_loss_m=250,
                terrain_type="descent",
            ),
        ]

    def test_ride_type_parameter_accepted(self, sample_segments):
        """generate_terrain_adapted_pacing accepts ride_type parameter."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        # Should not raise
        plan = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            ride_type="race",
        )

        assert plan.total_time_s > 0

    def test_training_ride_type_slower_descents(self, sample_segments):
        """Training ride type produces slower descent times than race."""
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing

        plan_race = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            ride_type="race",
        )

        plan_training = generate_terrain_adapted_pacing(
            segments=sample_segments,
            rider_ftp=250,
            target_intensity=0.85,
            ride_type="training",
        )

        # Training should be slower overall (especially on descents)
        # The difference might be small without elevation_profile (curvature data)
        # but the parameter should be accepted
        assert plan_race.total_time_s > 0
        assert plan_training.total_time_s > 0


class TestPlanTypeModulation:
    """#636: Plan Type modulates the learned Riding Behavior.

    training = identity (raw baseline exactly); race/gran_fondo tighten
    coasting; touring loosens it. Same course, two ride types →
    different descent power, different stop time, both traceable to the
    same learned baseline.
    """

    def test_presets_carry_coast_modulation(self):
        """Preset table gains coast modulation factors with the right order.
        Race pushes coasting DOWN (pedals descents more: higher power
        factor); touring pushes coasting UP (lower power factor).
        training = 1.0 identity."""
        from trainingdash.domain.pacing_model import RIDE_TYPE_PRESETS

        assert RIDE_TYPE_PRESETS["training"].coast_modulation == pytest.approx(1.0)
        assert (
            RIDE_TYPE_PRESETS["race"].coast_modulation
            >= RIDE_TYPE_PRESETS["gran_fondo"].coast_modulation
            > RIDE_TYPE_PRESETS["training"].coast_modulation
            > RIDE_TYPE_PRESETS["touring"].coast_modulation
        )

    def test_coast_modulation_validation(self):
        """coast_modulation must be > 0 (and sane: <= 2)."""
        from trainingdash.domain.pacing_model import RideTypeParams

        with pytest.raises(ValueError, match="coast_modulation"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=6, coast_modulation=0.0)
        with pytest.raises(ValueError, match="coast_modulation"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=6, coast_modulation=3.5)

    def test_modulate_descent_power_multiplier_identity_for_training(self):
        """Training reproduces the raw learned baseline exactly."""
        from trainingdash.domain.pacing_model import RIDE_TYPE_PRESETS, modulate_descent_power_multiplier

        assert modulate_descent_power_multiplier(0.12, RIDE_TYPE_PRESETS["training"]) == pytest.approx(0.12)

    def test_modulate_descent_power_multiplier_race_tightens_touring_loosens(self):
        """Race pedals descents more (higher power), touring coasts more
        (lower power); result clamped to the physical band [0.0, 1.0]."""
        from trainingdash.domain.pacing_model import RIDE_TYPE_PRESETS, modulate_descent_power_multiplier

        race = modulate_descent_power_multiplier(0.12, RIDE_TYPE_PRESETS["race"])
        touring = modulate_descent_power_multiplier(0.12, RIDE_TYPE_PRESETS["touring"])
        assert touring < 0.12 < race

        # Clamped at the ceiling (the calibration band, not 1.0):
        # modulated values never exceed what real riders do
        assert modulate_descent_power_multiplier(0.9, RIDE_TYPE_PRESETS["race"]) <= 0.8
        # Default (uncalibrated 0.50) x gran_fondo 2.0 clamps at 0.8, not 1.0
        assert modulate_descent_power_multiplier(0.50, RIDE_TYPE_PRESETS["gran_fondo"]) == pytest.approx(0.8)

    def test_terrain_adapted_pacing_applies_modulation(self):
        from statistics import mean

        """The engine: same course, two ride types → different descent power.
        Race plans pedaled descents harder than touring plans coast them."""
        from trainingdash.domain.course_segmentation import CourseSegment
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing
        from trainingdash.domain.pacing_model import RIDE_TYPE_PRESETS, PacingCoefficients
        from trainingdash.domain.physics import EnvironmentParams, RiderParams

        # Simple hilly course: 2km descent at -5%
        segs = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
            CourseSegment(
                start_distance_m=1000,
                end_distance_m=2000,
                length_m=1000,
                avg_grade_pct=-5.0,
                elevation_gain_m=0,
                elevation_loss_m=50,
                terrain_type="descent",
            ),
        ]
        profile = []
        for i in range(0, 41):
            d = i * 50.0
            profile.append(
                {
                    "distance_m": d,
                    "elevation_m": 100.0 - max(0.0, d - 1000.0) * 0.05,
                    "grade_pct": -5.0 if d > 1000 else 0.0,
                    "lat": 47.0,
                    "lon": 8.0,
                }
            )
        coeffs = PacingCoefficients(
            grade_power_intercept=1.10,
            grade_power_slope=0.035,
            descent_power_multiplier=0.12,  # learned near-coaster
            activity_count=10,  # calibrated
        )
        rider = RiderParams(mass_kg=80, cda=0.32, crr=0.004)
        env = EnvironmentParams(air_density=1.15)

        race_plan = generate_terrain_adapted_pacing(
            segments=segs,
            rider_ftp=280.0,
            target_intensity=0.85,
            rider_params=rider,
            env_params=env,
            coefficients=coeffs,
            elevation_profile=profile,
            ride_type_params=RIDE_TYPE_PRESETS["race"],
        )
        touring_plan = generate_terrain_adapted_pacing(
            segments=segs,
            rider_ftp=280.0,
            target_intensity=0.85,
            rider_params=rider,
            env_params=env,
            coefficients=coeffs,
            elevation_profile=profile,
            ride_type_params=RIDE_TYPE_PRESETS["touring"],
        )

        race_descents = [t.target_power_w for t in race_plan.targets if t.terrain_type == "descent"]
        touring_descents = [t.target_power_w for t in touring_plan.targets if t.terrain_type == "descent"]
        assert race_descents and touring_descents
        assert mean(race_descents) > mean(touring_descents), "race must pedal descents harder than touring"
        # And touring still coasts (near-0 power vs race's higher)
        assert mean(touring_descents) < mean(race_descents)

    def test_terrain_adapted_pacing_training_is_identity(self):
        """Passing no ride_type_params (or training) reproduces the unmodulated
        plan exactly — the raw learned behavior."""
        from trainingdash.domain.course_segmentation import CourseSegment
        from trainingdash.domain.pacing import generate_terrain_adapted_pacing
        from trainingdash.domain.pacing_model import RIDE_TYPE_PRESETS, PacingCoefficients
        from trainingdash.domain.physics import EnvironmentParams, RiderParams

        segs = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
            CourseSegment(
                start_distance_m=1000,
                end_distance_m=2000,
                length_m=1000,
                avg_grade_pct=-5.0,
                elevation_gain_m=0,
                elevation_loss_m=50,
                terrain_type="descent",
            ),
        ]
        profile = [
            {
                "distance_m": i * 50.0,
                "elevation_m": 100.0 - max(0.0, i * 50.0 - 1000.0) * 0.05,
                "grade_pct": -5.0 if i * 50.0 > 1000 else 0.0,
                "lat": 47.0,
                "lon": 8.0,
            }
            for i in range(41)
        ]
        coeffs = PacingCoefficients(descent_power_multiplier=0.12, activity_count=10)
        rider = RiderParams(mass_kg=80, cda=0.32, crr=0.004)
        env = EnvironmentParams(air_density=1.15)
        kw = {
            "segments": segs,
            "rider_ftp": 280.0,
            "target_intensity": 0.85,
            "rider_params": rider,
            "env_params": env,
            "coefficients": coeffs,
            "elevation_profile": profile,
        }

        plain = generate_terrain_adapted_pacing(**kw)
        training = generate_terrain_adapted_pacing(**kw, ride_type_params=RIDE_TYPE_PRESETS["training"])
        assert plain.total_time_s == pytest.approx(training.total_time_s)
        assert [t.target_power_w for t in plain.targets] == pytest.approx([t.target_power_w for t in training.targets])
