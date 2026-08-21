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
