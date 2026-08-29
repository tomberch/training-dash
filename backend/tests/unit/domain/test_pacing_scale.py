"""Scale-to-time solver tests (ADR 0005 #637).

Target-time plans scale the rider's terrain-shaped profile on pedaling
segments until riding time hits the target. Descents stay at coast
level (unchanged by scaling). Replaces the constant-power Mode A
optimizer (physiologically fictional: promised NP 175W for a ride that
costs NP 239W at the same pace).
"""

from statistics import mean

import pytest

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import generate_terrain_adapted_pacing
from trainingdash.domain.pacing_model import PacingCoefficients
from trainingdash.domain.physics import EnvironmentParams, RiderParams


def _hilly_segments():
    """2km flat + 2km climb (5%) + 2km descent (-5%)."""
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
            avg_grade_pct=5.0,
            elevation_gain_m=100,
            elevation_loss_m=0,
            terrain_type="climb",
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


def _hilly_profile():
    """Elevation profile matching the segments (50m steps, straight line)."""
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
    return profile


SEGS = _hilly_segments()
PROFILE = _hilly_profile()
RIDER = RiderParams(mass_kg=80, cda=0.32, crr=0.004)
ENV = EnvironmentParams(air_density=1.15)
COEFFS = PacingCoefficients(
    grade_power_intercept=1.10,
    grade_power_slope=0.035,
    descent_power_multiplier=0.12,  # learned near-coaster
    activity_count=10,
)


def _plan_kwargs():
    return {
        "segments": SEGS,
        "rider_ftp": 280.0,
        "rider_params": RIDER,
        "env_params": ENV,
        "coefficients": COEFFS,
        "elevation_profile": PROFILE,
    }


class TestScaleToTime:
    """The solver: scale pedaling power to hit a target riding time."""

    def test_scaled_plan_hits_target_time(self):
        from trainingdash.domain.pacing_scale import solve_target_time

        # Baseline shape at IF 0.85 — measure its riding time
        baseline = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.85)
        target = baseline.total_time_s * 0.9  # ask for 10% faster

        result = solve_target_time(
            **_plan_kwargs(),
            target_time_s=target,
        )

        assert result.plan.total_time_s == pytest.approx(target, rel=0.02)

    def test_descent_watts_unchanged_by_scaling(self):
        """Scaling moves pedaling power only; descent-point powers stay at
        coast level: base x descent_mult, identical before and after."""
        from trainingdash.domain.pacing_model import DESCENT_GRADE_PCT
        from trainingdash.domain.pacing_scale import solve_target_time

        baseline = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.85)
        result = solve_target_time(**_plan_kwargs(), target_time_s=baseline.total_time_s * 0.85)

        expected_coast = 280.0 * 0.85 * 0.12  # ftp x baseline_intensity x descent_mult
        descent_pts = [p for p, pt in zip(result.fine_powers, result.fine_points) if pt.grade_pct < DESCENT_GRADE_PCT]
        assert descent_pts, "fixture must contain descent points"
        assert descent_pts == pytest.approx([expected_coast] * len(descent_pts), rel=0.01)

        # And pedaling points scaled above baseline (0.85 x 1.10 formula floor)
        flat_pts = [p for p, pt in zip(result.fine_powers, result.fine_points) if abs(pt.grade_pct) < 0.5]
        assert mean(flat_pts) > 280.0 * 0.85 * 1.10  # scaled above the 0.85 shape

    def test_scaled_plan_is_terrain_shaped_not_constant(self):
        """VI of the scaled plan reflects terrain variability (> 1.05 on a
        hilly course), not the constant-power fantasy (VI ≈ 1.0)."""
        from trainingdash.domain.pacing_scale import solve_target_time

        baseline = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.85)
        result = solve_target_time(**_plan_kwargs(), target_time_s=baseline.total_time_s * 0.9)

        vi = result.plan.normalized_power_w / result.plan.avg_power_w if result.plan.avg_power_w else 1.0
        assert vi > 1.05

    def test_climb_power_rises_when_time_tightens(self):
        """Going faster means pedaling harder — on pedaling segments."""
        from trainingdash.domain.pacing_scale import solve_target_time

        baseline = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.85)
        climb_baseline = [t.target_power_w for t in baseline.targets if t.terrain_type == "climb"]

        result = solve_target_time(**_plan_kwargs(), target_time_s=baseline.total_time_s * 0.85)
        climb_scaled = [t.target_power_w for t in result.plan.targets if t.terrain_type == "climb"]

        assert mean(climb_scaled) > mean(climb_baseline)

    def test_infeasible_fast_target_hard_error_with_min_time(self):
        """Faster than physically possible → ValueError stating the minimum
        achievable time at max power."""
        from trainingdash.domain.pacing_scale import solve_target_time

        # Max-power plan: what's the floor?
        floor = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=1.5, power_cap_ftp_pct=1.5)
        impossible = floor.total_time_s * 0.5

        with pytest.raises(ValueError, match="too fast"):
            solve_target_time(**_plan_kwargs(), target_time_s=impossible, max_intensity=1.5)

    def test_slower_than_coast_hard_error_with_max_time(self):
        """Slower than the coasting floor → ValueError stating the maximum
        achievable time at minimum power."""
        from trainingdash.domain.pacing_scale import solve_target_time

        coast = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.3)
        impossible = coast.total_time_s * 2.0

        with pytest.raises(ValueError, match="too slow"):
            solve_target_time(**_plan_kwargs(), target_time_s=impossible, min_intensity=0.3)

    def test_solver_reports_scaling_factor(self):
        """The result exposes the intensity actually solved for — the UI
        can show what the target time demands."""
        from trainingdash.domain.pacing_scale import solve_target_time

        baseline = generate_terrain_adapted_pacing(**_plan_kwargs(), target_intensity=0.85)
        result = solve_target_time(**_plan_kwargs(), target_time_s=baseline.total_time_s * 0.9)

        assert result.solved_intensity > 0.85  # faster time = higher intensity
        assert result.converged is True
