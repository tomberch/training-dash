"""Unit tests for pacing_model module.

Tests the core pacing model coefficients, cornering physics, and Normalized Power.
"""

import math

import numpy as np
import pytest

from trainingdash.domain.pacing_model import (
    DEFAULT_COEFFICIENTS,
    DESCENT_GRADE_PCT,
    GRADE_POWER_INTERCEPT,
    GRADE_POWER_SLOPE,
    MAX_DESCENT_POWER_MULT,
    MAX_LAT_ACCEL,
    MAX_POWER_MULTIPLIER,
    MIN_LAT_ACCEL,
    MIN_POWER_MULTIPLIER,
    RIDE_TYPE_PRESETS,
    PacingCoefficients,
    RideTypeParams,
    RideTypePreset,
    a_lat_from_aggressiveness,
    calculate_curvature_menger,
    calculate_intensity_factor,
    calculate_normalized_power,
    cornering_speed_limit,
    effective_a_lat,
    effective_descent_power_multiplier,
    estimate_tss,
    get_grade_power_multiplier,
    modulate_descent_power_multiplier,
    resolve_ride_type_params,
)


# =============================================================================
# Test PacingCoefficients Dataclass
# =============================================================================


class TestPacingCoefficients:
    """Tests for PacingCoefficients dataclass."""

    def test_defaults_creation(self):
        """Creating defaults() should return correct default values."""
        defaults = PacingCoefficients.defaults()

        assert defaults.grade_power_intercept == 1.10
        assert defaults.grade_power_slope == 0.035
        assert defaults.max_descent_speed_mps == 18.0
        assert defaults.descent_power_multiplier == 0.50
        assert defaults.curvature_speed_coefficient == 4.8

    def test_default_instance_matches_defaults_method(self):
        """Default instance should match defaults() method."""
        instance = PacingCoefficients()
        defaults = PacingCoefficients.defaults()

        assert instance.grade_power_intercept == defaults.grade_power_intercept
        assert instance.grade_power_slope == defaults.grade_power_slope
        assert instance.max_descent_speed_mps == defaults.max_descent_speed_mps

    def test_custom_coefficients(self):
        """Custom coefficients should be stored correctly."""
        custom = PacingCoefficients(
            grade_power_intercept=1.15,
            grade_power_slope=0.04,
            max_descent_speed_mps=20.0,
            descent_power_multiplier=0.40,
            curvature_speed_coefficient=5.5,
        )

        assert custom.grade_power_intercept == 1.15
        assert custom.grade_power_slope == 0.04
        assert custom.max_descent_speed_mps == 20.0
        assert custom.descent_power_multiplier == 0.40
        assert custom.curvature_speed_coefficient == 5.5

    def test_provenance_fields_default_to_none(self):
        """Provenance metadata fields should default to None/0."""
        coef = PacingCoefficients()

        assert coef.user_id is None
        assert coef.bike_id is None
        assert coef.climb_sample_count == 0
        assert coef.descent_sample_count == 0
        assert coef.activity_count == 0
        assert coef.last_calibrated_at is None
        assert coef.terrain_behavior is None


# =============================================================================
# Test RideTypeParams
# =============================================================================


class TestRideTypeParams:
    """Tests for RideTypeParams dataclass."""

    def test_valid_params(self):
        """Valid parameters should be accepted."""
        params = RideTypeParams(descent_aggressiveness=70, stop_pct=6)

        assert params.descent_aggressiveness == 70
        assert params.stop_pct == 6.0
        assert params.coast_modulation == 1.0

    def test_valid_params_with_coast_modulation(self):
        """Coast modulation parameter should be accepted."""
        params = RideTypeParams(
            descent_aggressiveness=85, stop_pct=3, coast_modulation=2.0
        )

        assert params.coast_modulation == 2.0

    def test_descent_aggressiveness_too_low_raises(self):
        """Descent aggressiveness below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="descent_aggressiveness"):
            RideTypeParams(descent_aggressiveness=-1, stop_pct=6)

    def test_descent_aggressiveness_too_high_raises(self):
        """Descent aggressiveness above 100 should raise ValueError."""
        with pytest.raises(ValueError, match="descent_aggressiveness"):
            RideTypeParams(descent_aggressiveness=101, stop_pct=6)

    def test_stop_pct_too_low_raises(self):
        """Stop percentage below 0 should raise ValueError."""
        with pytest.raises(ValueError, match="stop_pct"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=-1)

    def test_stop_pct_too_high_raises(self):
        """Stop percentage above 50 should raise ValueError."""
        with pytest.raises(ValueError, match="stop_pct"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=51)

    def test_coast_modulation_zero_raises(self):
        """Coast modulation of 0 should raise ValueError."""
        with pytest.raises(ValueError, match="coast_modulation"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=6, coast_modulation=0)

    def test_coast_modulation_too_high_raises(self):
        """Coast modulation above 3 should raise ValueError."""
        with pytest.raises(ValueError, match="coast_modulation"):
            RideTypeParams(descent_aggressiveness=70, stop_pct=6, coast_modulation=3.1)

    def test_ride_type_for_curvature_aggressive(self):
        """High aggressiveness (>=80) should return 'race'."""
        params = RideTypeParams(descent_aggressiveness=80, stop_pct=0)
        assert params.ride_type_for_curvature == "race"

        params = RideTypeParams(descent_aggressiveness=100, stop_pct=0)
        assert params.ride_type_for_curvature == "race"

    def test_ride_type_for_curvature_cautious(self):
        """Low aggressiveness (<80) should return 'training'."""
        params = RideTypeParams(descent_aggressiveness=79, stop_pct=6)
        assert params.ride_type_for_curvature == "training"

        params = RideTypeParams(descent_aggressiveness=0, stop_pct=25)
        assert params.ride_type_for_curvature == "training"

    def test_stop_factor_calculation(self):
        """Stop factor should be 1 + (stop_pct / 100)."""
        params = RideTypeParams(descent_aggressiveness=70, stop_pct=6)
        assert params.stop_factor == pytest.approx(1.06)

        params = RideTypeParams(descent_aggressiveness=70, stop_pct=0)
        assert params.stop_factor == 1.0

        params = RideTypeParams(descent_aggressiveness=70, stop_pct=25)
        assert params.stop_factor == pytest.approx(1.25)


# =============================================================================
# Test Ride Type Presets
# =============================================================================


class TestRideTypePresets:
    """Tests for ride type presets."""

    def test_all_presets_exist(self):
        """All expected presets should exist."""
        expected = {"race", "gran_fondo", "training", "touring"}
        assert set(RIDE_TYPE_PRESETS.keys()) == expected

    def test_race_preset(self):
        """Race preset should have high aggressiveness, no stops."""
        preset = RIDE_TYPE_PRESETS["race"]
        assert preset.descent_aggressiveness == 90
        assert preset.stop_pct == 0
        assert preset.coast_modulation == 3.0

    def test_training_preset(self):
        """Training preset should be identity for coast modulation."""
        preset = RIDE_TYPE_PRESETS["training"]
        assert preset.descent_aggressiveness == 70
        assert preset.stop_pct == 6
        assert preset.coast_modulation == 1.0

    def test_touring_preset(self):
        """Touring preset should have more stops, lower aggressiveness."""
        preset = RIDE_TYPE_PRESETS["touring"]
        assert preset.descent_aggressiveness == 60
        assert preset.stop_pct == 25
        assert preset.coast_modulation == 0.5


class TestResolveRideTypeParams:
    """Tests for resolve_ride_type_params function."""

    def test_resolve_race(self):
        """Resolving 'race' should return race preset."""
        params = resolve_ride_type_params("race")
        assert params == RIDE_TYPE_PRESETS["race"]

    def test_resolve_training(self):
        """Resolving 'training' should return training preset."""
        params = resolve_ride_type_params("training")
        assert params == RIDE_TYPE_PRESETS["training"]

    def test_resolve_custom_with_params(self):
        """Custom type with params should return those params."""
        custom = RideTypeParams(descent_aggressiveness=65, stop_pct=10, coast_modulation=1.5)
        params = resolve_ride_type_params("custom", custom_params=custom)
        assert params == custom

    def test_resolve_custom_without_params_raises(self):
        """Custom type without params should raise ValueError."""
        with pytest.raises(ValueError, match="custom_params required"):
            resolve_ride_type_params("custom")

    def test_resolve_unknown_type_raises(self):
        """Unknown ride type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown ride_type"):
            resolve_ride_type_params("unknown")  # type: ignore


# =============================================================================
# Test Grade Power Multiplier
# =============================================================================


class TestGetGradePowerMultiplier:
    """Tests for get_grade_power_multiplier function."""

    def test_flat_terrain_uses_intercept(self):
        """Flat terrain (0% grade) should return intercept value."""
        result = get_grade_power_multiplier(0.0)
        assert result == pytest.approx(GRADE_POWER_INTERCEPT)

    def test_climb_increases_multiplier(self):
        """Climbing should increase the power multiplier."""
        flat = get_grade_power_multiplier(0.0)
        climb_5pct = get_grade_power_multiplier(5.0)
        climb_10pct = get_grade_power_multiplier(10.0)

        assert climb_5pct > flat
        assert climb_10pct > climb_5pct

    def test_descent_decreases_multiplier(self):
        """Descending should decrease the power multiplier."""
        flat = get_grade_power_multiplier(0.0)
        descent_5pct = get_grade_power_multiplier(-5.0)

        assert descent_5pct < flat

    def test_formula_calculation(self):
        """Verify the formula: intercept + slope * grade."""
        grade = 8.0
        expected = GRADE_POWER_INTERCEPT + GRADE_POWER_SLOPE * grade
        result = get_grade_power_multiplier(grade)
        assert result == pytest.approx(expected)

    def test_clamped_to_minimum(self):
        """Very steep descent should clamp to minimum."""
        result = get_grade_power_multiplier(-30.0)  # Very steep descent
        assert result >= MIN_POWER_MULTIPLIER

    def test_clamped_to_maximum(self):
        """Very steep climb should clamp to maximum."""
        result = get_grade_power_multiplier(30.0)  # Very steep climb
        assert result <= MAX_POWER_MULTIPLIER

    def test_with_custom_coefficients(self):
        """Custom coefficients should be used when provided."""
        custom = PacingCoefficients(
            grade_power_intercept=1.20,
            grade_power_slope=0.05,
        )
        result = get_grade_power_multiplier(5.0, coefficients=custom)
        expected = 1.20 + 0.05 * 5.0  # 1.45
        assert result == pytest.approx(expected)


# =============================================================================
# Test Cornering Physics
# =============================================================================


class TestALatFromAggressiveness:
    """Tests for a_lat_from_aggressiveness function."""

    def test_zero_aggressiveness(self):
        """Zero aggressiveness should give minimum lateral acceleration."""
        result = a_lat_from_aggressiveness(0)
        assert result == pytest.approx(MIN_LAT_ACCEL)

    def test_max_aggressiveness(self):
        """Max aggressiveness should give maximum lateral acceleration."""
        result = a_lat_from_aggressiveness(100)
        assert result == pytest.approx(MAX_LAT_ACCEL)

    def test_middle_aggressiveness(self):
        """50% aggressiveness should give midpoint lateral acceleration."""
        result = a_lat_from_aggressiveness(50)
        expected = (MIN_LAT_ACCEL + MAX_LAT_ACCEL) / 2
        assert result == pytest.approx(expected)

    def test_linear_interpolation(self):
        """Values should increase linearly with aggressiveness."""
        a_25 = a_lat_from_aggressiveness(25)
        a_50 = a_lat_from_aggressiveness(50)
        a_75 = a_lat_from_aggressiveness(75)

        # Check linear spacing
        assert (a_50 - a_25) == pytest.approx(a_75 - a_50)

    def test_invalid_negative_raises(self):
        """Negative aggressiveness should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-100"):
            a_lat_from_aggressiveness(-1)

    def test_invalid_over_100_raises(self):
        """Aggressiveness over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="must be 0-100"):
            a_lat_from_aggressiveness(101)


class TestCorneringSpeedLimit:
    """Tests for cornering_speed_limit function."""

    def test_straight_road_infinite_speed(self):
        """Straight road (curvature 0) should allow infinite speed."""
        result = cornering_speed_limit(0.0, a_lat=4.0)
        assert result == float("inf")

    def test_negative_curvature_infinite_speed(self):
        """Negative curvature (invalid) should allow infinite speed."""
        result = cornering_speed_limit(-0.01, a_lat=4.0)
        assert result == float("inf")

    def test_corner_speed_formula(self):
        """Verify formula: v = sqrt(a_lat / kappa)."""
        curvature = 0.01  # 100m radius corner
        a_lat = 4.0  # m/s²
        expected = math.sqrt(4.0 / 0.01)  # 20 m/s
        result = cornering_speed_limit(curvature, a_lat)
        assert result == pytest.approx(expected)

    def test_tighter_corner_slower_speed(self):
        """Tighter corners (higher curvature) should limit speed more."""
        a_lat = 4.0
        gentle = cornering_speed_limit(0.005, a_lat)  # 200m radius
        tight = cornering_speed_limit(0.02, a_lat)  # 50m radius

        assert tight < gentle

    def test_higher_a_lat_allows_faster(self):
        """Higher lateral acceleration allows faster cornering."""
        curvature = 0.01
        cautious = cornering_speed_limit(curvature, a_lat=2.0)
        aggressive = cornering_speed_limit(curvature, a_lat=6.0)

        assert aggressive > cautious

    def test_zero_a_lat_raises(self):
        """Zero a_lat should raise ValueError."""
        with pytest.raises(ValueError, match="a_lat must be positive"):
            cornering_speed_limit(0.01, a_lat=0.0)

    def test_negative_a_lat_raises(self):
        """Negative a_lat should raise ValueError."""
        with pytest.raises(ValueError, match="a_lat must be positive"):
            cornering_speed_limit(0.01, a_lat=-1.0)


class TestCalculateCurvatureMenger:
    """Tests for calculate_curvature_menger function."""

    def test_straight_line_zero_curvature(self):
        """Three collinear points should have zero curvature."""
        # Three points on a straight line (same longitude, different lat)
        result = calculate_curvature_menger(
            47.0, 8.0,  # Point 1
            47.001, 8.0,  # Point 2
            47.002, 8.0,  # Point 3
        )
        assert result == pytest.approx(0.0, abs=0.001)

    def test_tight_corner_high_curvature(self):
        """Three points forming a sharp turn should have high curvature."""
        # Form a right-angle turn
        result = calculate_curvature_menger(
            47.0, 8.0,
            47.0001, 8.0001,
            47.0, 8.0002,
        )
        assert result > 0

    def test_curvature_clamped_to_maximum(self):
        """Very tight corners should be clamped to max (0.05)."""
        # Extremely tight corner (nearly collinear with small deviation)
        result = calculate_curvature_menger(
            47.0, 8.0,
            47.00001, 8.00001,
            47.0, 8.00002,
        )
        assert result <= 0.05

    def test_degenerate_points_zero_curvature(self):
        """Coincident or very close points should return zero."""
        # Same point repeated
        result = calculate_curvature_menger(
            47.0, 8.0,
            47.0, 8.0,
            47.0, 8.0,
        )
        assert result == 0.0


class TestEffectiveALat:
    """Tests for effective_a_lat function."""

    def test_calibrated_coefficients_used(self):
        """Calibrated coefficients should be used when activity_count > 0."""
        coef = PacingCoefficients(
            curvature_speed_coefficient=5.5,
            activity_count=10,
        )
        result = effective_a_lat(coef, descent_aggressiveness=70)
        assert result == 5.5

    def test_uncalibrated_uses_aggressiveness_mapping(self):
        """Uncalibrated (activity_count=0) should use aggressiveness mapping."""
        coef = PacingCoefficients(
            curvature_speed_coefficient=5.5,
            activity_count=0,  # Not calibrated
        )
        result = effective_a_lat(coef, descent_aggressiveness=70)
        expected = a_lat_from_aggressiveness(70)
        assert result == pytest.approx(expected)

    def test_none_coefficients_uses_mapping(self):
        """None coefficients should use aggressiveness mapping."""
        result = effective_a_lat(None, descent_aggressiveness=50)
        expected = a_lat_from_aggressiveness(50)
        assert result == pytest.approx(expected)


class TestEffectiveDescentPowerMultiplier:
    """Tests for effective_descent_power_multiplier function."""

    def test_calibrated_coefficients_used(self):
        """Calibrated coefficients should be used when activity_count > 0."""
        coef = PacingCoefficients(
            descent_power_multiplier=0.35,
            activity_count=10,
        )
        result = effective_descent_power_multiplier(coef)
        assert result == 0.35

    def test_uncalibrated_uses_default(self):
        """Uncalibrated should use default descent power multiplier."""
        coef = PacingCoefficients(
            descent_power_multiplier=0.35,
            activity_count=0,  # Not calibrated
        )
        result = effective_descent_power_multiplier(coef)
        assert result == DEFAULT_COEFFICIENTS.descent_power_multiplier

    def test_none_coefficients_uses_default(self):
        """None coefficients should use default."""
        result = effective_descent_power_multiplier(None)
        assert result == DEFAULT_COEFFICIENTS.descent_power_multiplier


class TestModulateDescentPowerMultiplier:
    """Tests for modulate_descent_power_multiplier function."""

    def test_none_params_identity(self):
        """None ride type params should return base multiplier unchanged."""
        result = modulate_descent_power_multiplier(0.4, None)
        assert result == 0.4

    def test_training_type_identity(self):
        """Training type (coast_modulation=1.0) should return base unchanged."""
        params = RIDE_TYPE_PRESETS["training"]
        result = modulate_descent_power_multiplier(0.4, params)
        assert result == pytest.approx(0.4)

    def test_race_type_increases(self):
        """Race type should increase the multiplier (pedal descents more)."""
        params = RIDE_TYPE_PRESETS["race"]  # coast_modulation=3.0
        base = 0.12
        result = modulate_descent_power_multiplier(base, params)
        # 0.12 * 3.0 = 0.36 (within band)
        assert result == pytest.approx(0.36)

    def test_touring_type_decreases(self):
        """Touring type should decrease the multiplier (more coasting)."""
        params = RIDE_TYPE_PRESETS["touring"]  # coast_modulation=0.5
        base = 0.4
        result = modulate_descent_power_multiplier(base, params)
        # 0.4 * 0.5 = 0.2
        assert result == pytest.approx(0.2)

    def test_clamped_to_maximum(self):
        """Result should be clamped to MAX_DESCENT_POWER_MULT."""
        params = RideTypeParams(descent_aggressiveness=90, stop_pct=0, coast_modulation=3.0)
        base = 0.50
        result = modulate_descent_power_multiplier(base, params)
        # 0.50 * 3.0 = 1.5, should clamp to MAX_DESCENT_POWER_MULT (0.8)
        assert result <= MAX_DESCENT_POWER_MULT

    def test_clamped_to_minimum(self):
        """Result should be clamped to 0.0 minimum."""
        params = RideTypeParams(descent_aggressiveness=60, stop_pct=25, coast_modulation=0.01)
        base = 0.4
        result = modulate_descent_power_multiplier(base, params)
        assert result >= 0.0


# =============================================================================
# Test Normalized Power
# =============================================================================


class TestCalculateNormalizedPower:
    """Tests for calculate_normalized_power function."""

    def test_constant_power_equals_average(self):
        """Constant power should give NP equal to that power."""
        powers = np.full(300, 200.0)
        result = calculate_normalized_power(powers)
        assert result == pytest.approx(200.0, rel=0.01)

    def test_variable_power_higher_than_average(self):
        """Variable power should give NP higher than average."""
        # Alternating high/low power
        powers = np.concatenate([
            np.full(60, 150.0),
            np.full(60, 250.0),
            np.full(60, 150.0),
            np.full(60, 250.0),
        ])
        avg = np.mean(powers)  # 200
        result = calculate_normalized_power(powers)
        assert result > avg

    def test_short_data_returns_average(self):
        """Less than 30 samples should return simple average."""
        powers = np.array([200, 210, 220])
        result = calculate_normalized_power(powers)
        assert result == pytest.approx(np.mean(powers))

    def test_empty_array_returns_zero(self):
        """Empty array should return 0."""
        result = calculate_normalized_power(np.array([]))
        assert result == 0.0

    def test_different_sample_rate(self):
        """Sample rate should affect the window size."""
        powers = np.full(300, 200.0)
        result = calculate_normalized_power(powers, sample_rate_hz=2.0)
        assert result == pytest.approx(200.0, rel=0.01)


# =============================================================================
# Test Intensity Factor
# =============================================================================


class TestCalculateIntensityFactor:
    """Tests for calculate_intensity_factor function."""

    def test_at_ftp_equals_one(self):
        """NP at FTP should give IF of 1.0."""
        result = calculate_intensity_factor(250, 250)
        assert result == 1.0

    def test_below_ftp(self):
        """NP below FTP should give IF < 1.0."""
        result = calculate_intensity_factor(200, 250)
        assert result == pytest.approx(0.8)

    def test_above_ftp(self):
        """NP above FTP should give IF > 1.0."""
        result = calculate_intensity_factor(300, 250)
        assert result == pytest.approx(1.2)

    def test_zero_ftp_returns_zero(self):
        """Zero FTP should return 0 to avoid division by zero."""
        result = calculate_intensity_factor(200, 0)
        assert result == 0.0


# =============================================================================
# Test TSS Estimation
# =============================================================================


class TestEstimateTSS:
    """Tests for estimate_tss function."""

    def test_one_hour_at_ftp(self):
        """1 hour at FTP should give TSS of 100."""
        result = estimate_tss(np_watts=250, ftp=250, duration_s=3600)
        assert result == pytest.approx(100.0)

    def test_two_hours_at_ftp(self):
        """2 hours at FTP should give TSS of 200."""
        result = estimate_tss(np_watts=250, ftp=250, duration_s=7200)
        assert result == pytest.approx(200.0)

    def test_half_ftp_for_one_hour(self):
        """1 hour at IF=0.5 should give TSS of 25."""
        result = estimate_tss(np_watts=125, ftp=250, duration_s=3600)
        assert result == pytest.approx(25.0)

    def test_zero_duration_returns_zero(self):
        """Zero duration should return 0."""
        result = estimate_tss(np_watts=250, ftp=250, duration_s=0)
        assert result == 0.0

    def test_zero_ftp_returns_zero(self):
        """Zero FTP should return 0."""
        result = estimate_tss(np_watts=250, ftp=0, duration_s=3600)
        assert result == 0.0


# =============================================================================
# Test Module Constants
# =============================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_grade_power_constants_match_defaults(self):
        """Module constants should match default coefficients."""
        assert GRADE_POWER_INTERCEPT == DEFAULT_COEFFICIENTS.grade_power_intercept
        assert GRADE_POWER_SLOPE == DEFAULT_COEFFICIENTS.grade_power_slope

    def test_descent_grade_threshold(self):
        """Descent grade threshold should be negative."""
        assert DESCENT_GRADE_PCT < 0
        assert DESCENT_GRADE_PCT == -3.0

    def test_power_multiplier_bounds(self):
        """Power multiplier bounds should be reasonable."""
        assert MIN_POWER_MULTIPLIER > 0
        assert MIN_POWER_MULTIPLIER < 1.0
        assert MAX_POWER_MULTIPLIER > 1.0
        assert MAX_POWER_MULTIPLIER < 2.0

    def test_lateral_acceleration_bounds(self):
        """Lateral acceleration bounds should be reasonable."""
        assert MIN_LAT_ACCEL > 0
        assert MIN_LAT_ACCEL < MAX_LAT_ACCEL
        assert MAX_LAT_ACCEL <= 10  # Reasonable physical limit
