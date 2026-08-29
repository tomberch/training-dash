"""Unit tests for W'bal trajectory optimization."""

import numpy as np
import pytest

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.physics import RiderParams
from trainingdash.domain.wbal_trajectory_optimizer import (
    TrajectoryOptConfig,
    _compute_wbal_trajectory,
    _identify_recovery_opportunities,
    optimize_with_trajectory,
)


class TestComputeWbalTrajectory:
    """Tests for _compute_wbal_trajectory."""

    def test_no_depletion_below_cp(self):
        """Power below CP should not deplete W'bal."""
        powers = np.array([200.0, 200.0])
        times = np.array([60.0, 60.0])
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        # Power below CP means recovery (but starting at full W')
        assert final_wbal == w_prime
        assert min_wbal == w_prime
        assert len(wbal_series) == 2

    def test_depletion_above_cp(self):
        """Power above CP should deplete W'bal linearly."""
        powers = np.array([350.0])  # 100W above CP
        times = np.array([60.0])  # 60s = 6000J depletion
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        expected_final = 20000 - 6000  # 14000J
        assert final_wbal == expected_final
        assert min_wbal == expected_final
        assert wbal_series[-1] == expected_final

    def test_recovery_after_hard_effort(self):
        """W'bal should recover when power drops below CP."""
        powers = np.array([350.0, 150.0])  # Hard then easy
        times = np.array([60.0, 60.0])
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        # Minimum is after first segment (14000J)
        assert min_wbal == 14000
        # Final should be higher due to recovery but not full
        assert final_wbal > min_wbal
        assert final_wbal < w_prime

    def test_complete_depletion_clamps_to_zero(self):
        """W'bal cannot go negative."""
        powers = np.array([500.0])  # 250W above CP
        times = np.array([100.0])  # 25000J depletion, more than W'
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        assert final_wbal == 0
        assert min_wbal == 0

    def test_alternating_hard_easy(self):
        """Alternating hard/easy should show depletion/recovery pattern."""
        powers = np.array([350.0, 150.0, 350.0, 150.0])
        times = np.array([30.0, 30.0, 30.0, 30.0])
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        # Should have depleted twice, recovered twice (partially)
        assert len(wbal_series) == 4
        # Pattern should be: down, up, down, up
        assert wbal_series[0] < w_prime  # First depletion
        assert wbal_series[1] > wbal_series[0]  # First recovery
        assert wbal_series[2] < wbal_series[1]  # Second depletion
        assert wbal_series[3] > wbal_series[2]  # Second recovery

    def test_exactly_at_cp_no_change(self):
        """Power exactly at CP should not change W'bal."""
        powers = np.array([250.0])
        times = np.array([60.0])
        cp = 250.0
        w_prime = 20000.0

        min_wbal, final_wbal, wbal_series = _compute_wbal_trajectory(powers, times, cp, w_prime)

        # At CP, neither depleting nor recovering
        assert final_wbal == w_prime
        assert min_wbal == w_prime


class TestIdentifyRecoveryOpportunities:
    """Tests for _identify_recovery_opportunities."""

    def test_descent_is_recovery_opportunity(self):
        """Segments followed by descent are recovery opportunities."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=5.0,
                elevation_gain_m=50,
                elevation_loss_m=0,
                terrain_type="climb",
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

        mask = _identify_recovery_opportunities(segments)

        assert mask[0] == 1.0  # First segment precedes descent
        assert mask[1] == 0.0  # Last segment has no next

    def test_flat_after_long_section_is_partial_recovery(self):
        """Long flat sections are partial recovery opportunities."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=5.0,
                elevation_gain_m=50,
                elevation_loss_m=0,
                terrain_type="climb",
            ),
            CourseSegment(
                start_distance_m=1000,
                end_distance_m=2500,
                length_m=1500,
                avg_grade_pct=0.2,
                elevation_gain_m=3,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
        ]

        mask = _identify_recovery_opportunities(segments)

        assert mask[0] == 0.5  # Flat >500m is partial recovery

    def test_climb_not_recovery_opportunity(self):
        """Climb segments are not recovery opportunities."""
        segments = [
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
                avg_grade_pct=8.0,
                elevation_gain_m=80,
                elevation_loss_m=0,
                terrain_type="climb",
            ),
        ]

        mask = _identify_recovery_opportunities(segments)

        assert mask[0] == 0.0  # Climb follows, not recovery

    def test_short_flat_not_recovery(self):
        """Short flat sections are not marked as recovery."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=5.0,
                elevation_gain_m=50,
                elevation_loss_m=0,
                terrain_type="climb",
            ),
            CourseSegment(
                start_distance_m=1000,
                end_distance_m=1300,
                length_m=300,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
        ]

        mask = _identify_recovery_opportunities(segments)

        assert mask[0] == 0.0  # Short flat (<500m) is not marked

    def test_single_segment_all_zeros(self):
        """Single segment should have zero mask (no next segment)."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
        ]

        mask = _identify_recovery_opportunities(segments)

        assert len(mask) == 1
        assert mask[0] == 0.0


class TestOptimizeWithTrajectory:
    """Tests for optimize_with_trajectory."""

    @pytest.fixture
    def simple_course(self) -> list[CourseSegment]:
        """Simple 5km course with climb and descent."""
        return [
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
                avg_grade_pct=5.0,
                elevation_gain_m=50,
                elevation_loss_m=0,
                terrain_type="climb",
            ),
            CourseSegment(
                start_distance_m=2000,
                end_distance_m=3000,
                length_m=1000,
                avg_grade_pct=-5.0,
                elevation_gain_m=0,
                elevation_loss_m=50,
                terrain_type="descent",
            ),
            CourseSegment(
                start_distance_m=3000,
                end_distance_m=4000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
            CourseSegment(
                start_distance_m=4000,
                end_distance_m=5000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            ),
        ]

    def test_raises_on_empty_segments(self):
        """Should raise ValueError for empty segments."""
        with pytest.raises(ValueError, match="empty"):
            optimize_with_trajectory(
                segments=[],
                rider_ftp=280,
                rider_cp=250,
                rider_w_prime=20000,
                target_energy_kj=500,
            )

    def test_raises_on_invalid_ftp(self):
        """Should raise ValueError for non-positive FTP."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            )
        ]
        with pytest.raises(ValueError, match="ftp"):
            optimize_with_trajectory(
                segments=segments,
                rider_ftp=0,
                rider_cp=250,
                rider_w_prime=20000,
                target_energy_kj=500,
            )

    def test_raises_on_invalid_cp(self):
        """Should raise ValueError for non-positive CP."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            )
        ]
        with pytest.raises(ValueError, match="cp"):
            optimize_with_trajectory(
                segments=segments,
                rider_ftp=280,
                rider_cp=0,
                rider_w_prime=20000,
                target_energy_kj=500,
            )

    def test_raises_on_invalid_w_prime(self):
        """Should raise ValueError for non-positive W'."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            )
        ]
        with pytest.raises(ValueError, match="w_prime"):
            optimize_with_trajectory(
                segments=segments,
                rider_ftp=280,
                rider_cp=250,
                rider_w_prime=0,
                target_energy_kj=500,
            )

    def test_raises_on_invalid_energy(self):
        """Should raise ValueError for non-positive energy."""
        segments = [
            CourseSegment(
                start_distance_m=0,
                end_distance_m=1000,
                length_m=1000,
                avg_grade_pct=0.0,
                elevation_gain_m=0,
                elevation_loss_m=0,
                terrain_type="flat",
            )
        ]
        with pytest.raises(ValueError, match="energy"):
            optimize_with_trajectory(
                segments=segments,
                rider_ftp=280,
                rider_cp=250,
                rider_w_prime=20000,
                target_energy_kj=0,
            )

    def test_returns_optimized_plan(self, simple_course):
        """Should return an OptimizedPlan with targets."""
        result = optimize_with_trajectory(
            segments=simple_course,
            rider_ftp=280,
            rider_cp=250,
            rider_w_prime=20000,
            target_energy_kj=800,
            rider_params=RiderParams(mass_kg=83, cda=0.32, crr=0.004),
        )

        assert result is not None
        assert len(result.targets) == len(simple_course)
        assert result.total_time_s > 0
        assert result.total_distance_m == 5000
        assert result.avg_power_w > 0

    def test_plan_has_all_metrics(self, simple_course):
        """Plan should include all optimization metrics."""
        result = optimize_with_trajectory(
            segments=simple_course,
            rider_ftp=280,
            rider_cp=250,
            rider_w_prime=20000,
            target_energy_kj=800,
        )

        assert hasattr(result, "normalized_power_w")
        assert hasattr(result, "intensity_factor")
        assert hasattr(result, "wbal_min")
        assert hasattr(result, "converged")
        assert hasattr(result, "iterations")
        assert hasattr(result, "improvement_vs_constant_pct")
        assert hasattr(result, "improvement_vs_heuristic_pct")

    def test_plan_has_valid_power_targets(self, simple_course):
        """All targets should have reasonable power values."""
        result = optimize_with_trajectory(
            segments=simple_course,
            rider_ftp=280,
            rider_cp=250,
            rider_w_prime=20000,
            target_energy_kj=800,
        )

        for target in result.targets:
            # Power should be within reasonable bounds
            assert target.target_power_w > 0
            assert target.target_power_w < 1000  # No unreasonable spikes
            assert target.estimated_time_s > 0
            assert target.estimated_speed_mps > 0


class TestTrajectoryOptConfig:
    """Tests for TrajectoryOptConfig dataclass."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = TrajectoryOptConfig()

        assert config.finish_empty_weight == 0.001
        assert config.target_final_wbal_pct == 0.05
        assert config.strategic_depletion_weight == 0.0

    def test_inherits_from_optimization_config(self):
        """Should inherit base optimization config attributes."""
        config = TrajectoryOptConfig()

        assert hasattr(config, "power_bounds_pct")
        assert hasattr(config, "wbal_min_threshold")
        assert hasattr(config, "max_iterations")
        assert hasattr(config, "tolerance")
        assert hasattr(config, "method")

    def test_custom_values(self):
        """Should accept custom values."""
        config = TrajectoryOptConfig(
            finish_empty_weight=0.01,
            target_final_wbal_pct=0.10,
            strategic_depletion_weight=0.001,
        )

        assert config.finish_empty_weight == 0.01
        assert config.target_final_wbal_pct == 0.10
        assert config.strategic_depletion_weight == 0.001

    def test_frozen(self):
        """Config should be immutable."""
        from dataclasses import FrozenInstanceError

        config = TrajectoryOptConfig()
        with pytest.raises(FrozenInstanceError):
            config.finish_empty_weight = 0.5
