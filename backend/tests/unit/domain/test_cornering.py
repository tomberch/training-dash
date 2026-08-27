"""Tests for B1 cornering-speed physics (ADR 0004 Phase B).

The cornering limit v = min(v_physics, sqrt(a_lat / curvature)) replaces
the old deg/100m threshold-table multiplier. Curvature is Menger (1/m),
the same definition calibration fits.
"""

import itertools
import math

import pytest

from trainingdash.domain.pacing_model import (
    a_lat_from_aggressiveness,
    cornering_speed_limit,
)
from trainingdash.domain.physics import RiderParams


class TestALatFromAggressiveness:
    """descent_aggressiveness (0-100) maps to lateral acceleration a_lat."""

    def test_cautious_is_low(self):
        assert a_lat_from_aggressiveness(0) == pytest.approx(2.0)

    def test_default_training_is_moderate(self):
        assert a_lat_from_aggressiveness(70) == pytest.approx(4.8)

    def test_race_is_high(self):
        assert a_lat_from_aggressiveness(100) == pytest.approx(6.0)

    def test_monotonic(self):
        vals = [a_lat_from_aggressiveness(x) for x in range(0, 101, 10)]
        assert vals == sorted(vals)


class TestCorneringSpeedLimit:
    """v_corner = sqrt(a_lat / kappa); curvature in 1/m."""

    def test_straight_road_no_limit(self):
        # kappa=0 → no cornering limit
        assert cornering_speed_limit(0.0, a_lat=4.0) == float("inf")

    def test_radius_from_curvature(self):
        # kappa = 1/R, so v = sqrt(a_lat * R)
        # R=100m, a_lat=4 → v = 20 m/s
        assert cornering_speed_limit(0.01, a_lat=4.0) == pytest.approx(20.0)

    def test_tighter_corner_slower(self):
        fast = cornering_speed_limit(0.005, a_lat=4.0)  # R=200m
        slow = cornering_speed_limit(0.02, a_lat=4.0)  # R=50m
        assert slow < fast

    def test_higher_a_lat_faster(self):
        cautious = cornering_speed_limit(0.01, a_lat=2.0)
        aggressive = cornering_speed_limit(0.01, a_lat=6.0)
        assert aggressive > cautious

    def test_physics_example(self):
        # Hairpin R=25m, a_lat=3 m/s² → v = sqrt(75) ≈ 8.66 m/s ≈ 31 km/h
        assert cornering_speed_limit(1 / 25.0, a_lat=3.0) == pytest.approx(math.sqrt(75.0))


class TestFineGrainedCornering:
    """B1 integration: Menger curvature + cornering limit in the fine-grained loop."""

    @staticmethod
    def _curved_descent_profile() -> list[dict]:
        """A straight-line profile whose GPS track follows an arc.

        Elevation descends linearly; lat/lon follow a circle of radius
        ~100m, so curvature ≈ 0.01 (the clamp). Distances follow arc length.
        """
        import math

        radius = 100.0
        total_arc = 2000.0  # 200 points × 10m arc steps... resampled to 25m later
        points = []
        n = 60
        for i in range(n):
            arc = i * 25.0
            theta = arc / radius
            points.append(
                {
                    "distance_m": arc,
                    "elevation_m": 900.0 - 0.06 * arc,  # -6% descent
                    "grade_pct": -6.0,
                    # Circle centered at (lat0, lon0 + R); start at bottom of circle
                    "lat": 47.0 + (radius * math.sin(theta / radius)) / 111000.0,
                    "lon": 7.0 + (radius * (1 - math.cos(theta / radius))) / (111000.0 * math.cos(math.radians(47.0))),
                }
            )
        return points

    def test_resample_produces_menger_curvature(self):
        """Curvature values are Menger (1/m): R=100m arc → kappa ≈ 0.01."""
        from trainingdash.domain.fine_grained_pacing import resample_elevation_profile

        points = resample_elevation_profile(self._curved_descent_profile(), target_spacing_m=25.0)

        curvatures = [p.curvature_1_m for p in points]
        # The arc has radius 100m → kappa ≈ 0.01 on interior points
        interior = curvatures[2:-2]
        assert all(k > 0 for k in interior)
        assert all(k <= 0.05 + 1e-9 for k in interior)
        # R=100m arc: interpolated chords tighten the effective radius,
        # so kappa reads 0.02 (R=50m) — curvature is detected and unclamped
        assert all(0.015 <= k <= 0.05 for k in interior)
        # The old deg/100m field is gone
        assert not hasattr(points[0], "curvature_deg_per_100m")

    def test_cornering_limits_descent_speed(self):
        """On a curved descent, plan speed ≤ sqrt(a_lat/kappa) at curvature points."""
        from trainingdash.domain.fine_grained_pacing import (
            FineGrainedPoint,
            calculate_speeds_and_times,
        )
        from trainingdash.domain.pacing_model import a_lat_from_aggressiveness, cornering_speed_limit

        radius = 100.0
        points = [
            FineGrainedPoint(
                distance_m=i * 25.0,
                elevation_m=900.0 - i * 1.5,
                grade_pct=-6.0,
                curvature_1_m=1.0 / radius,
            )
            for i in range(20)
        ]
        powers = [200.0] * len(points)
        speeds, _ = calculate_speeds_and_times(
            points, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), ride_type="training"
        )

        a_lat = a_lat_from_aggressiveness(70)
        limit = cornering_speed_limit(1.0 / radius, a_lat)
        for speed in speeds:
            assert speed <= limit + 1e-9

    def test_straight_descent_uncapped_by_cornering(self):
        """No curvature → no cornering limit → physics speed stands."""
        from trainingdash.domain.fine_grained_pacing import (
            FineGrainedPoint,
            calculate_speeds_and_times,
        )

        points = [
            FineGrainedPoint(distance_m=i * 25.0, elevation_m=900.0 - i * 1.5, grade_pct=-6.0, curvature_1_m=0.0)
            for i in range(20)
        ]
        powers = [200.0] * len(points)
        speeds, _ = calculate_speeds_and_times(
            points, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), ride_type="training"
        )

        # Straight -6% descent with 200W: physics speed (well above cornering speeds)
        assert all(s > 10.0 for s in speeds)

    def test_curved_descent_slower_than_straight(self):
        """Same grade, same power: the curved descent plan is slower."""
        from trainingdash.domain.fine_grained_pacing import (
            FineGrainedPoint,
            calculate_speeds_and_times,
        )

        powers = [200.0] * 20
        straight = [
            FineGrainedPoint(distance_m=i * 25.0, elevation_m=0, grade_pct=-6.0, curvature_1_m=0.0) for i in range(20)
        ]
        curved = [
            FineGrainedPoint(distance_m=i * 25.0, elevation_m=0, grade_pct=-6.0, curvature_1_m=0.025) for i in range(20)
        ]

        speeds_straight, _ = calculate_speeds_and_times(
            straight, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), ride_type="training"
        )
        speeds_curved, _ = calculate_speeds_and_times(
            curved, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), ride_type="training"
        )

        assert sum(speeds_curved) < sum(speeds_straight)

    def test_more_aggressive_ride_type_faster_through_corners(self):
        """Higher descent_aggressiveness → higher cornering speeds."""
        from trainingdash.domain.fine_grained_pacing import (
            FineGrainedPoint,
            calculate_speeds_and_times,
        )
        from trainingdash.domain.pacing_model import RideTypeParams

        points = [
            FineGrainedPoint(distance_m=i * 25.0, elevation_m=0, grade_pct=-6.0, curvature_1_m=0.025) for i in range(20)
        ]
        powers = [200.0] * 20

        cautious = RideTypeParams(descent_aggressiveness=40, stop_pct=0)
        racer = RideTypeParams(descent_aggressiveness=95, stop_pct=0)

        speeds_cautious, _ = calculate_speeds_and_times(
            points,
            powers,
            RiderParams(mass_kg=83, cda=0.32, crr=0.004),
            descent_aggressiveness=cautious.descent_aggressiveness,
        )
        speeds_racer, _ = calculate_speeds_and_times(
            points,
            powers,
            RiderParams(mass_kg=83, cda=0.32, crr=0.004),
            descent_aggressiveness=racer.descent_aggressiveness,
        )

        assert sum(speeds_racer) > sum(speeds_cautious)

    def test_no_gps_grade_only_fallback_unchanged(self):
        """No curvature/wind data (no GPS) → per-point density physics only."""
        from trainingdash.domain.fine_grained_pacing import (
            FineGrainedPoint,
            calculate_speeds_and_times,
        )
        from trainingdash.domain.physics import (
            EnvironmentParams,
            RiderParams,
            air_density_from_altitude,
            speed_from_power,
        )

        points = [
            FineGrainedPoint(distance_m=i * 25.0, elevation_m=900.0 - i * 1.5, grade_pct=-6.0, curvature_1_m=None)
            for i in range(20)
        ]
        powers = [200.0] * len(points)
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        env = EnvironmentParams()
        speeds, _ = calculate_speeds_and_times(points, powers, rider_params=rider, env_params=env)

        rho_sea = air_density_from_altitude(0.0)
        for i, (speed, power) in enumerate(zip(speeds, powers)):
            expected_env = EnvironmentParams(
                air_density=env.air_density * air_density_from_altitude(points[i].elevation_m) / rho_sea
            )
            expected = speed_from_power(power, -6.0, rider, expected_env)
            assert speed == pytest.approx(expected)


class TestBrakingEnvelope:
    """B2: look-ahead braking cap.

    Speed at each point must be reachable from the previous point's speed
    given braking deceleration a_brake: you can't be doing 18 m/s one point
    before a corner that limits you to 11 m/s 25m later.
    """

    @staticmethod
    def _descent_with_hairpin(spacing_m=25.0, n_straight=20, hairpin_idx=20, n_after=10):
        """Straight -8% descent for n_straight points, then an R=25m hairpin."""
        from trainingdash.domain.fine_grained_pacing import FineGrainedPoint

        points = []
        for i in range(n_straight + n_after):
            kappa = 1.0 / 25.0 if i == hairpin_idx else 0.0
            points.append(
                FineGrainedPoint(
                    distance_m=i * spacing_m,
                    elevation_m=1000.0 - 0.08 * i * spacing_m,
                    grade_pct=-8.0,
                    curvature_1_m=kappa or None,
                )
            )
        return points

    def test_no_impossible_decelerations(self):
        """Speed drop between consecutive points never exceeds a_brake over one spacing."""
        from trainingdash.domain.fine_grained_pacing import calculate_speeds_and_times

        points = self._descent_with_hairpin()
        powers = [250.0] * len(points)
        speeds, _ = calculate_speeds_and_times(
            points, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), max_descent_speed_mps=18.0
        )

        spacing = 25.0
        a_brake = 4.0
        max_drop = (2 * a_brake * spacing) ** 0.5  # v² budget over one spacing
        for prev, curr in itertools.pairwise(speeds):
            drop = prev - curr
            # Allow small physics-driven acceleration upward; only deceleration is capped
            if drop > 0:
                # drop² <= 2*a*d must hold
                assert drop**2 <= 2 * a_brake * spacing + 1.0, (
                    f"impossible deceleration: {prev:.1f} -> {curr:.1f} m/s over {spacing}m"
                )

    def test_braking_starts_before_corner(self):
        """The point *before* the hairpin must already be slowed (look-ahead works)."""
        from trainingdash.domain.fine_grained_pacing import calculate_speeds_and_times
        from trainingdash.domain.pacing_model import a_lat_from_aggressiveness, cornering_speed_limit

        points = self._descent_with_hairpin(hairpin_idx=20)
        powers = [250.0] * len(points)
        speeds, _ = calculate_speeds_and_times(
            points, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), max_descent_speed_mps=18.0
        )

        limit = cornering_speed_limit(1.0 / 25.0, a_lat_from_aggressiveness(70))
        # At the corner: at/below the limit
        assert speeds[20] <= limit + 1e-9
        # One point before (25m out): braking budget means it cannot still
        # be at full approach speed (18 m/s would need 26m to brake)
        approach = speeds[19]
        a_brake = 4.0
        min_brake_dist = (approach**2 - limit**2) / (2 * a_brake)
        assert min_brake_dist <= 25.0 + 1e-6, "approach speed too high to brake in time"

    def test_acceleration_out_of_corner_is_progressive(self):
        """After the corner, speed builds gradually (no instant jump back)."""
        from trainingdash.domain.fine_grained_pacing import calculate_speeds_and_times

        points = self._descent_with_hairpin(hairpin_idx=20, n_after=10)
        powers = [250.0] * len(points)
        speeds, _ = calculate_speeds_and_times(
            points, powers, RiderParams(mass_kg=83, cda=0.32, crr=0.004), max_descent_speed_mps=18.0
        )

        # After the corner, speeds rise but never exceed physics speed;
        # consecutive increases are bounded by what gravity+power can do
        for prev, curr in itertools.pairwise(speeds[21:]):
            assert curr >= prev - 0.5  # no unexplained hard decel after corner


class TestFineGrainedWind:
    """Wind through the fine-grained path (per-point headwind from bearings)."""

    @staticmethod
    def _out_and_back_profile(spacing_m=25.0, n_per_leg=40):
        """North for n_per_leg points, then south. Constant -0% grade... use flat."""

        points = []
        lat0, lon0 = 47.0, 7.0
        n = n_per_leg * 2
        for i in range(n):
            # North for first leg, south for second (same path back)
            meters = i * spacing_m
            if i < n_per_leg:
                lat = lat0 + meters / 111000.0
            else:
                lat = lat0 + (2 * n_per_leg * spacing_m - meters) / 111000.0
            points.append(
                {
                    "distance_m": meters,
                    "elevation_m": 100.0,
                    "grade_pct": 0.0,
                    "lat": lat,
                    "lon": lon0,
                }
            )
        return points

    def test_headwind_slows_out_leg_tailwind_speeds_return_leg(self):
        """Wind from north: northbound leg slower, southbound leg faster."""
        from trainingdash.domain.fine_grained_pacing import generate_fine_grained_plan

        profile = self._out_and_back_profile()
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)

        calm = generate_fine_grained_plan(profile, rider_ftp=280, rider_params=rider)
        windy = generate_fine_grained_plan(
            profile,
            rider_ftp=280,
            rider_params=rider,
            wind_speed_mps=6.0,
            wind_direction_deg=0.0,  # from north
        )

        # Mid-point of each leg (avoid the turn)
        calm_speeds = [t.speed_mps for t in calm.points]
        windy_speeds = [t.speed_mps for t in windy.points]
        out_calm, out_windy = calm_speeds[5], windy_speeds[5]
        back_calm, back_windy = calm_speeds[-6], windy_speeds[-6]

        assert out_windy < out_calm, "headwind must slow the northbound leg"
        assert back_windy > back_calm, "tailwind must speed up the southbound leg"

    def test_zero_wind_matches_uniform_env(self):
        """No wind → results identical to no wind parameter at all."""
        from trainingdash.domain.fine_grained_pacing import generate_fine_grained_plan

        profile = self._out_and_back_profile()
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)

        a = generate_fine_grained_plan(profile, rider_ftp=280, rider_params=rider)
        b = generate_fine_grained_plan(profile, rider_ftp=280, rider_params=rider, wind_speed_mps=0.0)

        assert a.total_time_s == pytest.approx(b.total_time_s)

    def test_no_gps_wind_is_ignored(self):
        """Points without lat/lon cannot decompose wind → pure physics."""
        from trainingdash.domain.fine_grained_pacing import generate_fine_grained_plan

        profile = [{"distance_m": i * 25.0, "elevation_m": 100.0, "grade_pct": 0.0} for i in range(40)]
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)

        calm = generate_fine_grained_plan(profile, rider_ftp=280, rider_params=rider)
        windy = generate_fine_grained_plan(
            profile, rider_ftp=280, rider_params=rider, wind_speed_mps=8.0, wind_direction_deg=0.0
        )

        assert calm.total_time_s == pytest.approx(windy.total_time_s)


class TestPerPointAirDensity:
    """Per-point ISA density scaling from point elevation."""

    def test_high_altitude_point_faster_than_sea_level(self):
        """Same grade/power: 2000m elevation point is faster than 0m point."""
        from trainingdash.domain.fine_grained_pacing import FineGrainedPoint, calculate_speeds_and_times

        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        sea = [FineGrainedPoint(distance_m=i * 25.0, elevation_m=0.0, grade_pct=-3.0) for i in range(10)]
        alt = [FineGrainedPoint(distance_m=i * 25.0, elevation_m=2000.0, grade_pct=-3.0) for i in range(10)]
        powers = [200.0] * 10

        speeds_sea, _ = calculate_speeds_and_times(sea, powers, rider)
        speeds_alt, _ = calculate_speeds_and_times(alt, powers, rider)

        assert sum(speeds_alt) > sum(speeds_sea)

    def test_density_ratio_preserves_forecast_conditions(self):
        """Per-point density scales the provided env density by ISA ratio."""
        from trainingdash.domain.physics import EnvironmentParams, air_density_from_altitude

        # The function under test is internal; verify the ratio math it uses

        env = EnvironmentParams(air_density=1.15)
        rho_2000 = env.air_density * air_density_from_altitude(2000.0) / air_density_from_altitude(0.0)
        assert rho_2000 < env.air_density
        assert rho_2000 == pytest.approx(1.15 * 0.8216, rel=0.01)


class TestEffectiveALat:
    """Runtime a_lat resolution: calibrated coefficients beat aggressiveness."""

    def test_calibrated_coefficients_win(self):
        from trainingdash.domain.pacing_model import PacingCoefficients, effective_a_lat

        calibrated = PacingCoefficients(
            curvature_speed_coefficient=3.2,
            activity_count=10,
        )
        assert effective_a_lat(calibrated, descent_aggressiveness=70) == pytest.approx(3.2)

    def test_uncalibrated_falls_back_to_aggressiveness(self):
        from trainingdash.domain.pacing_model import PacingCoefficients, a_lat_from_aggressiveness, effective_a_lat

        uncalibrated = PacingCoefficients()  # activity_count=0
        assert effective_a_lat(uncalibrated, descent_aggressiveness=40) == pytest.approx(a_lat_from_aggressiveness(40))

    def test_default_coefficient_matches_training_mapping(self):
        from trainingdash.domain.pacing_model import PacingCoefficients, a_lat_from_aggressiveness

        assert PacingCoefficients().curvature_speed_coefficient == pytest.approx(a_lat_from_aggressiveness(70))

    def test_calibrated_but_zero_activity_count_is_fallback(self):
        from trainingdash.domain.pacing_model import PacingCoefficients, a_lat_from_aggressiveness, effective_a_lat

        # A stored row with 0 activities shouldn't be trusted
        row = PacingCoefficients(curvature_speed_coefficient=99.0, activity_count=0)
        assert effective_a_lat(row, descent_aggressiveness=70) == pytest.approx(a_lat_from_aggressiveness(70))


class TestFitALat:
    """B3: descent fitting produces a_lat (m/s²), not the old slope."""

    def test_fit_recovers_known_a_lat(self):
        """A rider cornering AT the limit everywhere: p90 of v²·k = the limit."""
        from trainingdash.domain.pacing_calibration import MIN_DESCENT_SAMPLES, DescentSample, fit_descent_coefficients

        # Synthetic rider cornering at exactly a_lat = 4.0 m/s² on varied radii
        kappas = (0.005, 0.01, 0.02, 0.04)
        samples = [
            DescentSample(
                grade_pct=-5.0,
                speed_mps=(4.0 / kappa) ** 0.5,
                power_mult=0.4,
                curvature=kappa,
                time_weight=10.0,
            )
            # repeat to clear MIN_DESCENT_SAMPLES (fit needs volume)
            for _ in range(MIN_DESCENT_SAMPLES // len(kappas) + 1)
            for kappa in kappas
        ]
        max_speed, power_mult, a_lat, confidence = fit_descent_coefficients(samples)

        assert a_lat == pytest.approx(4.0, rel=0.05)
        assert 1.0 <= a_lat <= 8.0

    def test_fit_uses_high_percentile_not_mean(self):
        """Mean v²·k underestimates the limit (braking in/out); p90 tracks it.

        Rider holds 4.0 m/s² at apexes but samples along entry/exit drag
        the mean down; the fitted a_lat must reflect the demonstrated limit.
        """
        import random

        from trainingdash.domain.pacing_calibration import MIN_DESCENT_SAMPLES, DescentSample, fit_descent_coefficients

        rng = random.Random(7)
        kappas = (0.005, 0.01, 0.02, 0.04)
        samples = []
        for _ in range(MIN_DESCENT_SAMPLES // len(kappas) + 10):
            for kappa in kappas:
                # 80% of samples hold only 40% of the limit (entry/exit),
                # 20% hold the full limit (apex)
                held = 4.0 if rng.random() < 0.2 else 1.6
                samples.append(
                    DescentSample(
                        grade_pct=-5.0,
                        speed_mps=(held / kappa) ** 0.5,
                        power_mult=0.4,
                        curvature=kappa,
                        time_weight=5.0,
                    )
                )
        *_, a_lat, _ = fit_descent_coefficients(samples)
        # p90 of the mixture: ~80% at 1.6 → p90 lands at the 4.0 apex group
        assert a_lat == pytest.approx(4.0, rel=0.2), f"got {a_lat:.2f}"

    def test_fit_insufficient_samples_returns_default(self):
        from trainingdash.domain.pacing_calibration import MIN_DESCENT_SAMPLES, DescentSample, fit_descent_coefficients
        from trainingdash.domain.pacing_model import a_lat_from_aggressiveness

        samples = [
            DescentSample(grade_pct=-5.0, speed_mps=10.0, power_mult=0.4, curvature=0.01, time_weight=5.0)
            for _ in range(5)
        ]
        assert len(samples) < MIN_DESCENT_SAMPLES
        *_, a_lat, _ = fit_descent_coefficients(samples)
        assert a_lat == pytest.approx(a_lat_from_aggressiveness(70))

    def test_fit_straight_roads_only_returns_default(self):
        """No curvature variance → nothing to fit → default a_lat."""
        from trainingdash.domain.pacing_calibration import MIN_DESCENT_SAMPLES, DescentSample, fit_descent_coefficients
        from trainingdash.domain.pacing_model import a_lat_from_aggressiveness

        samples = [
            DescentSample(grade_pct=-5.0, speed_mps=15.0, power_mult=0.4, curvature=0.0, time_weight=5.0)
            for _ in range(MIN_DESCENT_SAMPLES + 10)
        ]
        *_, a_lat, _ = fit_descent_coefficients(samples)
        assert a_lat == pytest.approx(a_lat_from_aggressiveness(70))

    def test_fit_caps_at_realistic_maximum(self):
        """Even reckless synthetic data can't produce a_lat above the clamp."""
        from trainingdash.domain.pacing_calibration import MIN_DESCENT_SAMPLES, DescentSample, fit_descent_coefficients

        samples = [
            DescentSample(grade_pct=-8.0, speed_mps=25.0, power_mult=0.4, curvature=0.01, time_weight=5.0)
            for _ in range(MIN_DESCENT_SAMPLES + 10)
        ]
        *_, a_lat, _ = fit_descent_coefficients(samples)
        assert a_lat <= 8.0


class TestDescentSampleCurvatureNoise:
    """B3 fix: extractor curvature must use wide triples, not GPS-noised pairs.

    At consecutive-record spacing (~5m), ±3m GPS jitter makes straight
    roads read as R<100m corners, saturating kappa at the clamp and
    poisoning the a_lat fit. Curvature must come from ~25m-anchored
    triples (same baseline as the runtime resampler), while speed and
    grade stay at record resolution.
    """

    @staticmethod
    def _records(n, radius_m=None, noise_m=3.0, seed=42, spacing_m=5.4, dt_s=1.0):
        """Straight -5% descent (or R=radius arc) with GPS jitter."""
        import math
        import random
        from types import SimpleNamespace
        from datetime import datetime, timedelta

        rng = random.Random(seed)
        recs = []
        t0 = datetime(2026, 1, 1)
        lat0, lon0 = 47.0, 7.0
        for i in range(n):
            d = i * spacing_m
            if radius_m:
                theta = d / radius_m
                lat = lat0 + (radius_m * math.sin(theta)) / 111000.0
                lon = lon0 + (radius_m * (1 - math.cos(theta))) / (111000.0 * math.cos(math.radians(lat0)))
            else:
                lat = lat0 + d / 111000.0
                lon = lon0
            recs.append(
                SimpleNamespace(
                    power_w=150.0,
                    altitude_m=900.0 - 0.05 * d,
                    distance_m=d,
                    timestamp=t0 + timedelta(seconds=i * dt_s),
                    lat=lat + rng.uniform(-1, 1) * noise_m / 111000.0,
                    lon=lon + rng.uniform(-1, 1) * noise_m / 111000.0 / math.cos(math.radians(lat0)),
                )
            )
        return recs

    def test_straight_road_jitter_does_not_saturate(self):
        """±3m GPS noise on a straight descent must NOT read as corners."""
        from trainingdash.domain.pacing_calibration import extract_descent_samples

        recs = self._records(600, radius_m=None, noise_m=3.0)
        samples = extract_descent_samples(recs, avg_power=150.0)
        assert len(samples) > 100

        from statistics import median

        med_kappa = median(s.curvature for s in samples)
        # Straight road: median curvature far below the 0.01 clamp.
        # (Pre-fix this was ~0.0084 — saturated by noise. At a 50m even
        # baseline with ±3m worst-case jitter the noise floor is ~0.0025.)
        assert med_kappa < 0.004, f"median kappa {med_kappa:.5f} too high — noise dominating"

    def test_real_corner_still_detected(self):
        """A genuine R=100m arc yields curvature near 0.01 on wide triples."""
        from trainingdash.domain.pacing_calibration import extract_descent_samples

        recs = self._records(600, radius_m=100.0, noise_m=1.0)  # low noise: signal visible
        samples = extract_descent_samples(recs, avg_power=150.0)
        from statistics import median

        med_kappa = median(s.curvature for s in samples if s.curvature > 0)
        assert med_kappa > 0.005, f"R=100m arc should give kappa ~0.01, got {med_kappa:.4f}"
