"""Validation tests for cycling physics model against reference values.

These tests validate our physics implementation against:
1. Known reference values from bikecalculator.com and gribble.org
2. ISA (International Standard Atmosphere) reference tables
3. Expected physical relationships

Per ticket #553, this validates the model is producing realistic values
that can be trusted for race pacing calculations.
"""

import time

import pytest

from trainingdash.domain.physics import (
    EnvironmentParams,
    RiderParams,
    air_density_from_altitude,
    power_required,
    speed_from_power,
)


class TestReferenceValuesFlatGround:
    """Validate power/speed against known reference values on flat ground.

    Reference values computed using Martin et al. physics model:
    - Rider + bike mass: 75kg + 8kg = 83kg
    - CdA: 0.32 m² (drops position)
    - Crr: 0.004 (good road tires)
    - Drivetrain efficiency: 97%
    - Air density: 1.225 kg/m³ (sea level ISA)

    These values are consistent with online calculators (onlycalculators.com,
    gribble.org) which use the same physics model with similar parameters.
    """

    @pytest.fixture
    def reference_rider(self):
        """Standard reference rider for validation."""
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    @pytest.fixture
    def sea_level_env(self):
        """Sea level environment."""
        return EnvironmentParams(air_density=1.225, wind_speed_mps=0)

    def test_30kmh_flat_power(self, reference_rider, sea_level_env):
        """30 km/h on flat should require ~140-150W."""
        speed = 30 / 3.6  # 8.33 m/s
        power = power_required(speed, 0, reference_rider, sea_level_env)

        # Model gives ~145W, online calculators give 138-150W
        assert 135 < power < 155, f"Expected ~145W, got {power:.1f}W"

    def test_35kmh_flat_power(self, reference_rider, sea_level_env):
        """35 km/h on flat should require ~210-225W."""
        speed = 35 / 3.6
        power = power_required(speed, 0, reference_rider, sea_level_env)

        assert 205 < power < 230, f"Expected ~218W, got {power:.1f}W"

    def test_40kmh_flat_power(self, reference_rider, sea_level_env):
        """40 km/h on flat should require ~305-325W."""
        speed = 40 / 3.6  # 11.11 m/s
        power = power_required(speed, 0, reference_rider, sea_level_env)

        # Model gives ~315W (online calculators ~304W with slightly lower CdA)
        assert 300 < power < 330, f"Expected ~315W, got {power:.1f}W"

    def test_45kmh_flat_power(self, reference_rider, sea_level_env):
        """45 km/h on flat should require ~425-450W."""
        speed = 45 / 3.6
        power = power_required(speed, 0, reference_rider, sea_level_env)

        assert 420 < power < 455, f"Expected ~437W, got {power:.1f}W"

    def test_50kmh_flat_power(self, reference_rider, sea_level_env):
        """50 km/h on flat should require ~575-605W."""
        speed = 50 / 3.6  # 13.89 m/s
        power = power_required(speed, 0, reference_rider, sea_level_env)

        assert 570 < power < 610, f"Expected ~588W, got {power:.1f}W"

    def test_200w_flat_speed(self, reference_rider, sea_level_env):
        """200W on flat should produce ~33-35 km/h."""
        speed = speed_from_power(200, 0, reference_rider, sea_level_env)
        speed_kmh = speed * 3.6

        assert 32.5 < speed_kmh < 35.5, f"Expected ~34 km/h, got {speed_kmh:.1f} km/h"

    def test_250w_flat_speed(self, reference_rider, sea_level_env):
        """250W on flat should produce ~36-38 km/h."""
        speed = speed_from_power(250, 0, reference_rider, sea_level_env)
        speed_kmh = speed * 3.6

        assert 35.5 < speed_kmh < 38.5, f"Expected ~37 km/h, got {speed_kmh:.1f} km/h"

    def test_300w_flat_speed(self, reference_rider, sea_level_env):
        """300W on flat should produce ~39-41 km/h."""
        speed = speed_from_power(300, 0, reference_rider, sea_level_env)
        speed_kmh = speed * 3.6

        assert 38.5 < speed_kmh < 41.5, f"Expected ~40 km/h, got {speed_kmh:.1f} km/h"


class TestReferenceValuesClimbing:
    """Validate power/speed on climbs where gravity dominates.

    On climbs, power is dominated by the gravity term:
    P ≈ m * g * sin(θ) * v / η

    For a 5% grade: sin(arctan(0.05)) ≈ 0.0499
    """

    @pytest.fixture
    def reference_rider(self):
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    def test_5pct_climb_15kmh(self, reference_rider):
        """15 km/h on 5% climb should require ~195-215W."""
        # Gravity: 83 * 9.81 * 0.0499 * 4.17 / 0.97 ≈ 174W
        # Plus rolling (~14W) + aero (~3.5W) ≈ 203W total
        speed = 15 / 3.6
        power = power_required(speed, 5, reference_rider)

        assert 195 < power < 215, f"Expected ~203W, got {power:.1f}W"

    def test_8pct_climb_12kmh(self, reference_rider):
        """12 km/h on 8% climb should require ~230-255W."""
        speed = 12 / 3.6
        power = power_required(speed, 8, reference_rider)

        assert 230 < power < 255, f"Expected ~242W, got {power:.1f}W"

    def test_10pct_climb_10kmh(self, reference_rider):
        """10 km/h on 10% climb should require ~235-260W."""
        speed = 10 / 3.6
        power = power_required(speed, 10, reference_rider)

        assert 235 < power < 260, f"Expected ~246W, got {power:.1f}W"

    def test_300w_on_5pct_climb(self, reference_rider):
        """300W on 5% climb should produce ~20-23 km/h."""
        speed = speed_from_power(300, 5, reference_rider)
        speed_kmh = speed * 3.6

        assert 19 < speed_kmh < 23, f"Expected ~21 km/h, got {speed_kmh:.1f} km/h"

    def test_300w_on_8pct_climb(self, reference_rider):
        """300W on 8% climb should produce ~14-16 km/h."""
        speed = speed_from_power(300, 8, reference_rider)
        speed_kmh = speed * 3.6

        assert 13.5 < speed_kmh < 16.5, f"Expected ~14.7 km/h, got {speed_kmh:.1f} km/h"

    def test_400w_on_10pct_climb(self, reference_rider):
        """400W on 10% climb should produce ~15-17 km/h."""
        speed = speed_from_power(400, 10, reference_rider)
        speed_kmh = speed * 3.6

        assert 14.5 < speed_kmh < 17.5, f"Expected ~15.9 km/h, got {speed_kmh:.1f} km/h"


class TestAirDensityISAReference:
    """Validate ISA air density against official reference values.

    ISA (International Standard Atmosphere) reference table values
    from aviation and meteorology standards.
    """

    # ISA reference values: (altitude_m, density_kg_m3)
    ISA_REFERENCE = [
        (0, 1.2250),
        (500, 1.1673),
        (1000, 1.1117),
        (1500, 1.0581),
        (2000, 1.0066),
        (2500, 0.9569),
        (3000, 0.9091),
        (4000, 0.8191),
        (5000, 0.7361),
    ]

    @pytest.mark.parametrize("altitude,expected_density", ISA_REFERENCE)
    def test_isa_reference_values(self, altitude, expected_density):
        """Air density should match ISA reference within 1%."""
        calculated = air_density_from_altitude(altitude)

        # 1% tolerance for rounding in reference tables
        assert calculated == pytest.approx(expected_density, rel=0.01), (
            f"At {altitude}m: expected {expected_density:.4f}, got {calculated:.4f}"
        )


class TestAltitudeEffects:
    """Validate altitude effects on power requirements."""

    @pytest.fixture
    def reference_rider(self):
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    def test_2000m_altitude_power_savings(self, reference_rider):
        """At 2000m altitude, ~15-18% less power for same speed (aero portion)."""
        speed = 40 / 3.6

        env_sea = EnvironmentParams(air_density=air_density_from_altitude(0))
        env_2000m = EnvironmentParams(air_density=air_density_from_altitude(2000))

        p_sea = power_required(speed, 0, reference_rider, env_sea)
        p_2000m = power_required(speed, 0, reference_rider, env_2000m)

        # Air density ratio: 1.007 / 1.225 ≈ 0.82
        # But only aero power scales with density (not rolling)
        # So total savings should be ~15% at 40 km/h
        savings_pct = (p_sea - p_2000m) / p_sea * 100

        assert 12 < savings_pct < 20, f"Expected ~15% savings, got {savings_pct:.1f}%"

    def test_altitude_speed_increase(self, reference_rider):
        """At 2000m altitude, same power should give ~3-5% more speed."""
        power = 250

        env_sea = EnvironmentParams(air_density=air_density_from_altitude(0))
        env_2000m = EnvironmentParams(air_density=air_density_from_altitude(2000))

        v_sea = speed_from_power(power, 0, reference_rider, env_sea)
        v_2000m = speed_from_power(power, 0, reference_rider, env_2000m)

        speed_gain_pct = (v_2000m - v_sea) / v_sea * 100

        # Due to cube root relationship, ~18% density reduction → ~5-6% speed gain
        assert 3 < speed_gain_pct < 7, f"Expected ~5% speed gain, got {speed_gain_pct:.1f}%"


class TestTTBikeComparison:
    """Validate TT bike vs road bike differences."""

    @pytest.fixture
    def road_rider(self):
        """Road bike in drops position."""
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    @pytest.fixture
    def tt_rider(self):
        """TT bike in aero position."""
        return RiderParams(mass_kg=83, cda=0.24, crr=0.003, efficiency=0.97)

    def test_tt_bike_power_savings(self, road_rider, tt_rider):
        """TT bike should save ~70-90W at 40 km/h."""
        speed = 40 / 3.6

        p_road = power_required(speed, 0, road_rider)
        p_tt = power_required(speed, 0, tt_rider)

        savings = p_road - p_tt

        # CdA reduction: (0.32 - 0.24) / 0.32 = 25%
        # Crr reduction: (0.004 - 0.003) / 0.004 = 25%
        # At 40 km/h, aero is ~75% of total, rolling ~10%
        # Expected savings: ~25% * 75% + 25% * 10% ≈ 21% ≈ 66W
        # But with lower Crr too, total is ~79W
        assert 65 < savings < 95, f"Expected ~79W savings, got {savings:.1f}W"

    def test_tt_bike_speed_gain(self, road_rider, tt_rider):
        """TT bike should be ~3-5 km/h faster at same power."""
        power = 280  # ~40 km/h road bike power

        v_road = speed_from_power(power, 0, road_rider) * 3.6
        v_tt = speed_from_power(power, 0, tt_rider) * 3.6

        speed_gain = v_tt - v_road

        assert 3 < speed_gain < 5.5, f"Expected ~4 km/h gain, got {speed_gain:.1f} km/h"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def reference_rider(self):
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    def test_very_steep_climb_low_power(self, reference_rider):
        """Very steep climb with low power should produce slow but positive speed."""
        # 100W on 15% grade
        speed = speed_from_power(100, 15, reference_rider)

        # Should be positive but very slow
        assert speed > 0
        assert speed * 3.6 < 8  # Less than 8 km/h

    def test_steep_descent_moderate_power(self, reference_rider):
        """Steep descent with moderate power should produce high speed."""
        # 150W on -8% grade - enough power that solver should converge
        speed = speed_from_power(150, -8, reference_rider)

        # Gravity assists significantly
        assert speed > 0
        speed_kmh = speed * 3.6
        # Should be faster than flat due to gravity assist
        flat_speed_kmh = speed_from_power(150, 0, reference_rider) * 3.6
        assert speed_kmh > flat_speed_kmh

    def test_near_threshold_power_on_steep_climb(self, reference_rider):
        """Near-threshold power on steep climb should converge."""
        # Just enough power to make progress on 12% grade
        speed = speed_from_power(350, 12, reference_rider)

        assert speed > 0
        speed_kmh = speed * 3.6
        assert 7 < speed_kmh < 12

    def test_high_power_on_flat(self, reference_rider):
        """Very high power on flat should produce high speed."""
        # 600W (sprint-level power)
        speed = speed_from_power(600, 0, reference_rider)

        speed_kmh = speed * 3.6
        # Should be ~52-56 km/h
        assert 50 < speed_kmh < 58


class TestSolverPerformance:
    """Test Newton-Raphson solver performance requirements."""

    @pytest.fixture
    def reference_rider(self):
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    def test_single_call_under_1ms(self, reference_rider):
        """Single speed_from_power call should complete in <1ms."""
        start = time.perf_counter()
        for _ in range(100):
            speed_from_power(250, 5, reference_rider)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 1, f"Average call took {avg_ms:.3f}ms, expected <1ms"

    def test_100_segment_course_under_100ms(self, reference_rider):
        """Simulating 100-segment course should complete in <100ms."""
        # Simulate varying grades like a real course
        grades = [0, 2, 4, 6, 8, 5, 3, 0, -2, -4] * 10  # 100 segments
        power = 250

        start = time.perf_counter()
        for grade in grades:
            speed_from_power(power, grade, reference_rider)
        elapsed = time.perf_counter() - start

        elapsed_ms = elapsed * 1000
        assert elapsed_ms < 100, f"100 segments took {elapsed_ms:.1f}ms, expected <100ms"

    def test_convergence_count(self, reference_rider):
        """Solver should converge in <10 iterations for normal cases."""
        # This is a behavioral test - we can't directly count iterations
        # but we can verify the result is accurate (implying convergence)
        test_cases = [
            (200, 0),
            (300, 5),
            (250, -3),
            (400, 10),
        ]

        for power, grade in test_cases:
            speed = speed_from_power(power, grade, reference_rider)
            power_back = power_required(speed, grade, reference_rider)

            # If solver converged properly, round-trip should be accurate
            assert power_back == pytest.approx(
                power, abs=0.01
            ), f"Failed for {power}W @ {grade}%: got {power_back:.2f}W back"


class TestPhysicalRelationships:
    """Validate expected physical relationships hold."""

    @pytest.fixture
    def reference_rider(self):
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.97)

    def test_doubling_mass_doubles_climb_power(self, reference_rider):
        """Doubling mass should roughly double power on steep climb."""
        heavy_rider = RiderParams(mass_kg=166, cda=0.32, crr=0.004, efficiency=0.97)

        speed = 12 / 3.6
        grade = 10  # Steep enough that gravity dominates

        p_normal = power_required(speed, grade, reference_rider)
        p_heavy = power_required(speed, grade, heavy_rider)

        # On steep climb, gravity ≈ 90% of resistance
        # So doubling mass should roughly double power
        ratio = p_heavy / p_normal
        assert 1.85 < ratio < 2.15, f"Expected ~2x, got {ratio:.2f}x"

    def test_cda_proportional_to_aero_power(self, reference_rider):
        """Halving CdA should roughly halve aero power component."""
        aero_rider = RiderParams(mass_kg=83, cda=0.16, crr=0.004, efficiency=0.97)

        # High speed where aero dominates
        speed = 50 / 3.6

        p_normal = power_required(speed, 0, reference_rider)
        p_aero = power_required(speed, 0, aero_rider)

        # At 50 km/h, aero is ~85% of total
        # Halving CdA saves ~42.5% of total power
        savings_pct = (p_normal - p_aero) / p_normal * 100
        assert 38 < savings_pct < 47, f"Expected ~42% savings, got {savings_pct:.1f}%"

    def test_efficiency_inversely_affects_power(self, reference_rider):
        """Lower efficiency should require more power input."""
        inefficient_rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004, efficiency=0.90)

        speed = 35 / 3.6

        p_normal = power_required(speed, 0, reference_rider)
        p_inefficient = power_required(speed, 0, inefficient_rider)

        # 0.97 / 0.90 = 1.078 → 7.8% more power needed
        ratio = p_inefficient / p_normal
        expected_ratio = 0.97 / 0.90
        assert ratio == pytest.approx(expected_ratio, rel=0.01)
