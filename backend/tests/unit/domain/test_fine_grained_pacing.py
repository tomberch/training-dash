"""Tests for fine-grained pacing module."""

import numpy as np
import pytest

from trainingdash.domain.fine_grained_pacing import (
    FineGrainedPoint,
    aggregate_to_display_segments,
    calculate_np_from_fine_grained,
    calculate_power_targets,
    calculate_speeds_and_times,
    generate_fine_grained_plan,
    resample_elevation_profile,
)
from trainingdash.domain.physics import EnvironmentParams, RiderParams


class TestResampleElevationProfile:
    """Tests for elevation profile resampling."""

    def test_empty_profile_returns_empty(self):
        result = resample_elevation_profile([])
        assert result == []

    def test_single_point_returns_empty(self):
        profile = [{"distance_m": 0, "elevation_m": 100, "grade_pct": 0}]
        result = resample_elevation_profile(profile)
        assert result == []

    def test_resamples_to_target_spacing(self):
        # 1000m course with 100m original spacing
        profile = [
            {"distance_m": i * 100, "elevation_m": 100 + i * 5, "grade_pct": 5.0}
            for i in range(11)
        ]

        result = resample_elevation_profile(profile, target_spacing_m=25.0)

        # Should have ~40 points for 1000m at 25m spacing
        assert len(result) >= 40
        assert len(result) <= 42

        # Check spacing is consistent
        for i in range(1, len(result)):
            spacing = result[i].distance_m - result[i - 1].distance_m
            assert 20 <= spacing <= 30  # Allow some tolerance

    def test_preserves_start_and_end_distance(self):
        profile = [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 500, "elevation_m": 125, "grade_pct": 5.0},
            {"distance_m": 1000, "elevation_m": 150, "grade_pct": 5.0},
        ]

        result = resample_elevation_profile(profile, target_spacing_m=25.0)

        assert result[0].distance_m == 0
        assert result[-1].distance_m == 1000

    def test_calculates_grades_correctly(self):
        # Flat section followed by 10% climb
        profile = [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 100, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 200, "elevation_m": 110, "grade_pct": 10.0},
        ]

        result = resample_elevation_profile(profile, target_spacing_m=25.0)

        # Due to smoothing, grades will transition gradually
        # Just verify the general trend: first points flatter than last points
        early_grades = [p.grade_pct for p in result if p.distance_m < 50]
        late_grades = [p.grade_pct for p in result if 150 < p.distance_m < 200]

        # Early section should have lower average grade than late section
        assert np.mean(early_grades) < np.mean(late_grades)


class TestCalculatePowerTargets:
    """Tests for terrain-adapted power targets."""

    def test_flat_terrain_uses_base_multiplier(self):
        points = [FineGrainedPoint(0, 100, 0.0)]  # Flat
        powers = calculate_power_targets(
            points, base_power_w=200, grade_power_intercept=1.10, grade_power_slope=0.035
        )

        # Flat: multiplier = 1.10, power = 200 * 1.10 = 220
        assert powers[0] == pytest.approx(220, rel=0.01)

    def test_climb_increases_power(self):
        points = [FineGrainedPoint(0, 100, 10.0)]  # 10% climb
        powers = calculate_power_targets(
            points, base_power_w=200, grade_power_intercept=1.10, grade_power_slope=0.035
        )

        # 10% climb: multiplier = 1.10 + 0.035*10 = 1.45, power = 200 * 1.45 = 290
        assert powers[0] == pytest.approx(290, rel=0.01)

    def test_descent_reduces_power(self):
        points = [FineGrainedPoint(0, 100, -10.0)]  # 10% descent
        powers = calculate_power_targets(
            points, base_power_w=200, grade_power_intercept=1.10, grade_power_slope=0.035
        )

        # -10% descent: multiplier = 1.10 + 0.035*(-10) = 0.75
        # But clamped to min 0.50, so power = 200 * 0.75 = 150
        assert powers[0] == pytest.approx(150, rel=0.01)

    def test_steep_descent_clamps_to_minimum(self):
        points = [FineGrainedPoint(0, 100, -20.0)]  # 20% descent
        powers = calculate_power_targets(
            points, base_power_w=200, grade_power_intercept=1.10, grade_power_slope=0.035
        )

        # -20%: multiplier = 1.10 - 0.7 = 0.40, clamped to 0.50
        assert powers[0] == pytest.approx(100, rel=0.01)  # 200 * 0.50

    def test_steep_climb_clamps_to_maximum(self):
        points = [FineGrainedPoint(0, 100, 20.0)]  # 20% climb
        powers = calculate_power_targets(
            points, base_power_w=200, grade_power_intercept=1.10, grade_power_slope=0.035
        )

        # 20%: multiplier = 1.10 + 0.7 = 1.80, clamped to 1.50
        assert powers[0] == pytest.approx(300, rel=0.01)  # 200 * 1.50

    def test_power_cap_applied(self):
        points = [FineGrainedPoint(0, 100, 10.0)]
        powers = calculate_power_targets(
            points, base_power_w=200, power_cap_w=250  # Cap below natural target
        )

        # Natural would be 290W, but capped to 250
        assert powers[0] == 250


class TestCalculateSpeedsAndTimes:
    """Tests for physics-based speed and time calculation."""

    @pytest.fixture
    def rider(self):
        return RiderParams(mass_kg=80, cda=0.32, crr=0.004)

    def test_flat_terrain_reasonable_speed(self, rider):
        points = [
            FineGrainedPoint(0, 100, 0.0),
            FineGrainedPoint(100, 100, 0.0),
        ]
        powers = [200, 200]

        speeds, times = calculate_speeds_and_times(points, powers, rider)

        # 200W on flat should give ~32-36 km/h (~9-10 m/s)
        assert 8 < speeds[0] < 11
        assert times[0] == pytest.approx(100 / speeds[0], rel=0.01)

    def test_climb_reduces_speed(self, rider):
        points = [
            FineGrainedPoint(0, 100, 8.0),  # 8% climb
            FineGrainedPoint(100, 108, 8.0),
        ]
        powers = [250, 250]

        speeds, times = calculate_speeds_and_times(points, powers, rider)

        # 250W on 8% climb should give ~12-16 km/h (~3.5-4.5 m/s)
        assert 3 < speeds[0] < 5

    def test_descent_increases_speed(self, rider):
        points = [
            FineGrainedPoint(0, 100, -5.0),  # 5% descent
            FineGrainedPoint(100, 95, -5.0),
        ]
        powers = [100, 100]  # Light pedaling on descent

        speeds, times = calculate_speeds_and_times(points, powers, rider)

        # Descent with light pedaling should be fast
        assert speeds[0] > 10  # > 36 km/h

    def test_max_descent_speed_applied(self, rider):
        points = [
            FineGrainedPoint(0, 100, -10.0),
            FineGrainedPoint(100, 90, -10.0),
        ]
        powers = [150, 150]

        speeds, _ = calculate_speeds_and_times(
            points, powers, rider, max_descent_speed_mps=15.0
        )

        assert speeds[0] <= 15.0


class TestCalculateNPFromFineGrained:
    """Tests for normalized power calculation."""

    def test_constant_power_np_equals_average(self):
        powers = [200] * 100
        times = [1.0] * 100  # 100 seconds total

        np_power, samples = calculate_np_from_fine_grained(powers, times)

        # Constant power: NP should equal average
        assert np_power == pytest.approx(200, rel=0.02)

    def test_variable_power_np_higher_than_average(self):
        # Alternating high/low power with longer periods (simulates terrain variation)
        # Need segments longer than 30s so they survive the rolling average
        powers = [300] * 20 + [100] * 20 + [300] * 20 + [100] * 20  # 80 samples
        times = [1.0] * 80  # Average power = 200

        np_power, samples = calculate_np_from_fine_grained(powers, times)

        # Variable power: NP should be higher than average due to 4th power weighting
        # The alternating pattern creates variability that the 4th power captures
        assert np_power > 200

    def test_returns_power_samples(self):
        powers = [200, 250, 300]
        times = [10, 5, 15]  # 30 seconds total

        _, samples = calculate_np_from_fine_grained(powers, times)

        # Should expand to per-second samples
        assert len(samples) == 30
        assert samples[:10].tolist() == [200] * 10
        assert samples[10:15].tolist() == [250] * 5
        assert samples[15:].tolist() == [300] * 15

    def test_short_duration_returns_average(self):
        powers = [200, 220]
        times = [5, 5]  # Only 10 seconds - too short for NP

        np_power, _ = calculate_np_from_fine_grained(powers, times)

        # Should return something close to average
        expected_avg = (200 * 5 + 220 * 5) / 10
        assert np_power == pytest.approx(expected_avg, rel=0.05)


class TestGenerateFineGrainedPlan:
    """Integration tests for the main entry point."""

    @pytest.fixture
    def simple_profile(self):
        """A simple 1km course: 500m flat + 500m 5% climb."""
        return [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 250, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 500, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 750, "elevation_m": 112.5, "grade_pct": 5.0},
            {"distance_m": 1000, "elevation_m": 125, "grade_pct": 5.0},
        ]

    def test_generates_plan_with_points(self, simple_profile):
        plan = generate_fine_grained_plan(
            simple_profile,
            rider_ftp=300,
            target_intensity=0.85,
        )

        # Should have many fine-grained points
        assert len(plan.points) > 30

        # Total distance should match
        assert plan.total_distance_m == pytest.approx(1000, rel=0.01)

    def test_variable_power_across_terrain(self, simple_profile):
        plan = generate_fine_grained_plan(
            simple_profile,
            rider_ftp=300,
            target_intensity=0.85,
        )

        # Find flat and climb points
        flat_powers = [p.power_w for p in plan.points if p.distance_m < 400]
        climb_powers = [p.power_w for p in plan.points if p.distance_m > 600]

        # Climb should have higher power than flat
        assert np.mean(climb_powers) > np.mean(flat_powers)

    def test_variable_speed_across_terrain(self, simple_profile):
        plan = generate_fine_grained_plan(
            simple_profile,
            rider_ftp=300,
            target_intensity=0.85,
        )

        flat_speeds = [p.speed_mps for p in plan.points if p.distance_m < 400]
        climb_speeds = [p.speed_mps for p in plan.points if p.distance_m > 600]

        # Flat should be faster than climb
        assert np.mean(flat_speeds) > np.mean(climb_speeds)

    def test_total_time_reasonable(self, simple_profile):
        plan = generate_fine_grained_plan(
            simple_profile,
            rider_ftp=300,
            target_intensity=0.85,
        )

        # 1km at ~25-30 km/h average should take ~120-150 seconds
        assert 100 < plan.total_time_s < 200

    def test_np_calculated(self, simple_profile):
        plan = generate_fine_grained_plan(
            simple_profile,
            rider_ftp=300,
            target_intensity=0.85,
        )

        # NP should be reasonable
        assert 200 < plan.normalized_power_w < 350


class TestAggregateToDisplaySegments:
    """Tests for aggregating fine points to display segments."""

    @pytest.fixture
    def sample_plan(self):
        """Create a sample fine-grained plan for testing."""
        from trainingdash.domain.fine_grained_pacing import FineGrainedPlan, FineGrainedTarget

        points = [
            FineGrainedTarget(i * 25, 0.0, 220, 9.0, 2.78)  # 25m at 9m/s = 2.78s
            for i in range(40)  # 1000m total
        ]

        return FineGrainedPlan(
            points=points,
            total_time_s=sum(p.time_s for p in points),
            total_distance_m=975,  # 39 segments * 25m
            avg_power_w=220,
            normalized_power_w=220,
            power_samples=np.array([220] * 111),
        )

    def test_aggregates_to_target_count(self, sample_plan):
        segments = aggregate_to_display_segments(sample_plan, target_segment_count=5)

        # Should have ~5 segments (may be fewer if min length dominates)
        assert 3 <= len(segments) <= 7

    def test_segments_have_required_fields(self, sample_plan):
        segments = aggregate_to_display_segments(sample_plan, target_segment_count=5)

        for seg in segments:
            assert "segment_idx" in seg
            assert "start_distance_m" in seg
            assert "end_distance_m" in seg
            assert "distance_m" in seg
            assert "avg_grade_pct" in seg
            assert "avg_power_w" in seg
            assert "avg_speed_mps" in seg
            assert "time_s" in seg
            assert "terrain_type" in seg

    def test_segments_cover_full_distance(self, sample_plan):
        segments = aggregate_to_display_segments(sample_plan, target_segment_count=5)

        assert segments[0]["start_distance_m"] == 0
        # Last segment should end at or near total distance
        assert segments[-1]["end_distance_m"] >= sample_plan.total_distance_m * 0.9

    def test_empty_plan_returns_empty(self):
        from trainingdash.domain.fine_grained_pacing import FineGrainedPlan

        empty_plan = FineGrainedPlan(
            points=[], total_time_s=0, total_distance_m=0,
            avg_power_w=0, normalized_power_w=0, power_samples=np.array([])
        )

        segments = aggregate_to_display_segments(empty_plan)
        assert segments == []



class TestCurvatureCalculation:
    """Tests for curvature calculation from GPS coordinates."""

    def test_straight_road_zero_curvature(self):
        """A straight road should have zero curvature."""
        from trainingdash.domain.fine_grained_pacing import calculate_curvature

        # Straight line going north
        points = [
            FineGrainedPoint(distance_m=0, elevation_m=100, grade_pct=0, lat=47.0, lon=7.0),
            FineGrainedPoint(distance_m=100, elevation_m=100, grade_pct=0, lat=47.001, lon=7.0),
            FineGrainedPoint(distance_m=200, elevation_m=100, grade_pct=0, lat=47.002, lon=7.0),
            FineGrainedPoint(distance_m=300, elevation_m=100, grade_pct=0, lat=47.003, lon=7.0),
        ]

        curvatures = calculate_curvature(points)

        # All curvatures should be near zero
        assert all(c < 2 for c in curvatures)

    def test_90_degree_turn_high_curvature(self):
        """A 90 degree turn should have high curvature."""
        from trainingdash.domain.fine_grained_pacing import calculate_curvature

        # L-shaped path: go east, then turn north
        points = [
            FineGrainedPoint(distance_m=0, elevation_m=100, grade_pct=0, lat=47.0, lon=7.0),
            FineGrainedPoint(distance_m=100, elevation_m=100, grade_pct=0, lat=47.0, lon=7.001),  # east
            FineGrainedPoint(distance_m=200, elevation_m=100, grade_pct=0, lat=47.001, lon=7.001),  # north
            FineGrainedPoint(distance_m=300, elevation_m=100, grade_pct=0, lat=47.002, lon=7.001),  # north
        ]

        curvatures = calculate_curvature(points)

        # Middle point should have high curvature (90 degree turn)
        assert curvatures[1] > 30  # Should be significant turn

    def test_no_gps_returns_zeros(self):
        """Points without GPS coordinates should return zero curvature."""
        from trainingdash.domain.fine_grained_pacing import calculate_curvature

        points = [
            FineGrainedPoint(distance_m=0, elevation_m=100, grade_pct=0, lat=None, lon=None),
            FineGrainedPoint(distance_m=100, elevation_m=100, grade_pct=0, lat=None, lon=None),
            FineGrainedPoint(distance_m=200, elevation_m=100, grade_pct=0, lat=None, lon=None),
        ]

        curvatures = calculate_curvature(points)

        assert all(c == 0 for c in curvatures)


class TestCurvatureSpeedFactor:
    """Tests for curvature-based speed reduction."""

    def test_straight_descent_no_reduction(self):
        """Straight descents should have no speed reduction."""
        from trainingdash.domain.fine_grained_pacing import get_curvature_speed_factor

        factor = get_curvature_speed_factor(curvature_deg_per_100m=2.0, grade_pct=-5.0)
        assert factor == 1.0

    def test_curvy_descent_reduced_speed(self):
        """Curvy descents should have reduced speed."""
        from trainingdash.domain.fine_grained_pacing import get_curvature_speed_factor

        # Training mode
        factor = get_curvature_speed_factor(
            curvature_deg_per_100m=25.0, grade_pct=-5.0, ride_type="training"
        )
        assert factor == 0.90

        # Hairpin
        factor = get_curvature_speed_factor(
            curvature_deg_per_100m=40.0, grade_pct=-5.0, ride_type="training"
        )
        assert factor == 0.80

    def test_climb_no_reduction_even_if_curvy(self):
        """Climbs should have no speed reduction regardless of curvature."""
        from trainingdash.domain.fine_grained_pacing import get_curvature_speed_factor

        # Hairpin on a climb
        factor = get_curvature_speed_factor(curvature_deg_per_100m=50.0, grade_pct=5.0)
        assert factor == 1.0

    def test_race_mode_less_aggressive_reduction(self):
        """Race mode should have less aggressive speed reductions."""
        from trainingdash.domain.fine_grained_pacing import get_curvature_speed_factor

        # Same hairpin, different modes
        training_factor = get_curvature_speed_factor(
            curvature_deg_per_100m=40.0, grade_pct=-5.0, ride_type="training"
        )
        race_factor = get_curvature_speed_factor(
            curvature_deg_per_100m=40.0, grade_pct=-5.0, ride_type="race"
        )

        # Race should be faster (higher factor)
        assert race_factor > training_factor


class TestResampleWithGPS:
    """Tests for resampling with GPS coordinates."""

    def test_resamples_with_lat_lon(self):
        """Resampling should interpolate lat/lon when provided."""
        profile = [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": 0, "lat": 47.0, "lon": 7.0},
            {"distance_m": 100, "elevation_m": 105, "grade_pct": 5, "lat": 47.001, "lon": 7.0},
            {"distance_m": 200, "elevation_m": 110, "grade_pct": 5, "lat": 47.002, "lon": 7.0},
        ]

        result = resample_elevation_profile(profile, target_spacing_m=50.0)

        # Should have GPS coordinates
        assert result[0].lat is not None
        assert result[0].lon is not None

        # First point should be near original
        assert abs(result[0].lat - 47.0) < 0.0001

    def test_calculates_curvature_during_resample(self):
        """Resampling should calculate curvature from GPS."""
        # Create a curvy path
        profile = [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": -5, "lat": 47.0, "lon": 7.0},
            {"distance_m": 50, "elevation_m": 97, "grade_pct": -5, "lat": 47.0, "lon": 7.0005},
            {"distance_m": 100, "elevation_m": 95, "grade_pct": -5, "lat": 47.0005, "lon": 7.001},
            {"distance_m": 150, "elevation_m": 92, "grade_pct": -5, "lat": 47.001, "lon": 7.001},
        ]

        result = resample_elevation_profile(profile, target_spacing_m=25.0)

        # Should have curvature values
        has_curvature = any(p.curvature_deg_per_100m > 0 for p in result)
        assert has_curvature or len(result) < 3  # Either has curvature or too few points
