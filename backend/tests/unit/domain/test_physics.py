"""Unit tests for physics module."""

import math

import pytest

from trainingdash.domain.physics import (
    GRAVITY,
    SEA_LEVEL_AIR_DENSITY,
    EnvironmentParams,
    RiderParams,
    air_density_from_altitude,
    calculate_bearing,
    calculate_headwind,
    estimate_cp_from_ftp,
    estimate_ftp_from_cp,
    power_required,
    speed_from_power,
    time_for_segment,
)

# =============================================================================
# Test RiderParams
# =============================================================================


class TestRiderParams:
    """Tests for RiderParams dataclass validation."""

    def test_valid_params(self):
        """Valid parameters should create instance."""
        rider = RiderParams(mass_kg=75, cda=0.32, crr=0.004)
        assert rider.mass_kg == 75
        assert rider.cda == 0.32
        assert rider.crr == 0.004
        assert rider.efficiency == 0.97  # default

    def test_custom_efficiency(self):
        """Custom efficiency should be accepted."""
        rider = RiderParams(mass_kg=75, cda=0.32, crr=0.004, efficiency=0.98)
        assert rider.efficiency == 0.98

    def test_negative_mass_raises(self):
        """Negative mass should raise ValueError."""
        with pytest.raises(ValueError, match="mass_kg"):
            RiderParams(mass_kg=-1, cda=0.32, crr=0.004)

    def test_zero_mass_raises(self):
        """Zero mass should raise ValueError."""
        with pytest.raises(ValueError, match="mass_kg"):
            RiderParams(mass_kg=0, cda=0.32, crr=0.004)

    def test_negative_cda_raises(self):
        """Negative CdA should raise ValueError."""
        with pytest.raises(ValueError, match="cda"):
            RiderParams(mass_kg=75, cda=-0.1, crr=0.004)

    def test_zero_cda_raises(self):
        """Zero CdA should raise ValueError."""
        with pytest.raises(ValueError, match="cda"):
            RiderParams(mass_kg=75, cda=0, crr=0.004)

    def test_negative_crr_raises(self):
        """Negative Crr should raise ValueError."""
        with pytest.raises(ValueError, match="crr"):
            RiderParams(mass_kg=75, cda=0.32, crr=-0.001)

    def test_zero_crr_allowed(self):
        """Zero Crr should be allowed (frictionless)."""
        rider = RiderParams(mass_kg=75, cda=0.32, crr=0)
        assert rider.crr == 0

    def test_invalid_efficiency_raises(self):
        """Efficiency outside (0, 1] should raise ValueError."""
        with pytest.raises(ValueError, match="efficiency"):
            RiderParams(mass_kg=75, cda=0.32, crr=0.004, efficiency=0)

        with pytest.raises(ValueError, match="efficiency"):
            RiderParams(mass_kg=75, cda=0.32, crr=0.004, efficiency=1.1)


# =============================================================================
# Test EnvironmentParams
# =============================================================================


class TestEnvironmentParams:
    """Tests for EnvironmentParams dataclass."""

    def test_defaults(self):
        """Default values should be sea level, no wind."""
        env = EnvironmentParams()
        assert env.air_density == SEA_LEVEL_AIR_DENSITY
        assert env.wind_speed_mps == 0.0

    def test_custom_values(self):
        """Custom values should be accepted."""
        env = EnvironmentParams(air_density=1.1, wind_speed_mps=5.0)
        assert env.air_density == 1.1
        assert env.wind_speed_mps == 5.0

    def test_negative_air_density_raises(self):
        """Negative air density should raise ValueError."""
        with pytest.raises(ValueError, match="air_density"):
            EnvironmentParams(air_density=-1)

    def test_zero_air_density_raises(self):
        """Zero air density should raise ValueError."""
        with pytest.raises(ValueError, match="air_density"):
            EnvironmentParams(air_density=0)

    def test_negative_wind_allowed(self):
        """Negative wind (tailwind) should be allowed."""
        env = EnvironmentParams(wind_speed_mps=-10.0)
        assert env.wind_speed_mps == -10.0


# =============================================================================
# Test air_density_from_altitude
# =============================================================================


class TestAirDensityFromAltitude:
    """Tests for ISA air density calculation."""

    def test_sea_level(self):
        """Sea level should return standard density."""
        density = air_density_from_altitude(0)
        assert density == pytest.approx(SEA_LEVEL_AIR_DENSITY, rel=0.001)

    def test_1000m_altitude(self):
        """1000m altitude should reduce density by ~9%."""
        density = air_density_from_altitude(1000)
        # Expected: ~1.112 kg/m³
        assert density == pytest.approx(1.112, rel=0.01)
        assert density < SEA_LEVEL_AIR_DENSITY

    def test_2000m_altitude(self):
        """2000m altitude should reduce density by ~18%."""
        density = air_density_from_altitude(2000)
        # Expected: ~1.007 kg/m³
        assert density == pytest.approx(1.007, rel=0.01)

    def test_negative_altitude_clamped_to_zero(self):
        """Negative altitude should be treated as sea level."""
        density = air_density_from_altitude(-100)
        assert density == pytest.approx(SEA_LEVEL_AIR_DENSITY, rel=0.001)

    def test_above_troposphere_clamped(self):
        """Altitude above 11km should be clamped."""
        density_11k = air_density_from_altitude(11000)
        density_15k = air_density_from_altitude(15000)
        assert density_11k == pytest.approx(density_15k, rel=0.001)

    def test_density_decreases_with_altitude(self):
        """Higher altitude should always have lower density."""
        d_0 = air_density_from_altitude(0)
        d_500 = air_density_from_altitude(500)
        d_1000 = air_density_from_altitude(1000)
        d_2000 = air_density_from_altitude(2000)

        assert d_0 > d_500 > d_1000 > d_2000


# =============================================================================
# Test power_required
# =============================================================================


class TestPowerRequired:
    """Tests for power_required function."""

    @pytest.fixture
    def rider(self) -> RiderParams:
        """Standard test rider."""
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004)

    def test_zero_speed_returns_zero(self, rider):
        """Zero speed should require zero power."""
        power = power_required(0, 0, rider)
        assert power == 0.0

    def test_negative_speed_returns_zero(self, rider):
        """Negative speed should return zero."""
        power = power_required(-5, 0, rider)
        assert power == 0.0

    def test_flat_road_typical_speed(self, rider):
        """Flat road at 30 km/h should require ~150W."""
        speed_mps = 30 / 3.6  # ~8.33 m/s
        power = power_required(speed_mps, 0, rider)
        # Typical value for 83kg rider with CdA=0.32
        assert 140 < power < 160

    def test_flat_road_40kph(self, rider):
        """Flat road at 40 km/h should require ~300W (aero dominates)."""
        speed_mps = 40 / 3.6  # ~11.11 m/s
        power = power_required(speed_mps, 0, rider)
        # v³ relationship means 33% more speed needs ~2x power
        # 83kg rider with CdA=0.32 needs ~315W at 40 km/h
        assert 280 < power < 350

    def test_climb_increases_power(self, rider):
        """5% climb should significantly increase power requirement."""
        speed_mps = 5.0  # ~18 km/h (typical climbing speed)
        power_flat = power_required(speed_mps, 0, rider)
        power_climb = power_required(speed_mps, 5.0, rider)

        # On 5% grade, gravity dominates
        assert power_climb > power_flat * 2

    def test_steep_climb(self, rider):
        """10% climb at low speed should be mostly gravity."""
        speed_mps = 3.0  # ~11 km/h
        power = power_required(speed_mps, 10.0, rider)

        # Gravity component: m * g * sin(θ) * v / η
        # sin(10%) ≈ 0.0995
        gravity_component = 83 * GRAVITY * math.sin(math.atan(0.1)) * 3.0 / 0.97
        # Power should be close to gravity component (aero negligible at low speed)
        assert abs(power - gravity_component) / gravity_component < 0.2

    def test_descent_low_power(self, rider):
        """Steep descent should require little power (gravity assists)."""
        speed_mps = 10.0  # ~36 km/h
        power = power_required(speed_mps, -8.0, rider)

        # On steep descent, gravity assists - power can be near zero
        assert power >= 0  # Never negative (clamped)
        assert power < 100  # Much less than flat at same speed

    def test_headwind_increases_power(self, rider):
        """Headwind should increase power requirement."""
        speed_mps = 10.0
        env_no_wind = EnvironmentParams()
        env_headwind = EnvironmentParams(wind_speed_mps=5.0)

        power_no_wind = power_required(speed_mps, 0, rider, env_no_wind)
        power_headwind = power_required(speed_mps, 0, rider, env_headwind)

        # 5 m/s headwind at 10 m/s ground speed = 50% more airspeed
        assert power_headwind > power_no_wind * 1.3

    def test_tailwind_decreases_power(self, rider):
        """Tailwind should decrease power requirement."""
        speed_mps = 10.0
        env_no_wind = EnvironmentParams()
        env_tailwind = EnvironmentParams(wind_speed_mps=-5.0)

        power_no_wind = power_required(speed_mps, 0, rider, env_no_wind)
        power_tailwind = power_required(speed_mps, 0, rider, env_tailwind)

        assert power_tailwind < power_no_wind

    def test_altitude_decreases_power(self, rider):
        """Higher altitude (thinner air) should decrease power at same speed."""
        speed_mps = 11.0  # ~40 km/h where aero matters
        env_sea = EnvironmentParams(air_density=1.225)
        env_high = EnvironmentParams(air_density=1.0)  # ~2000m altitude

        power_sea = power_required(speed_mps, 0, rider, env_sea)
        power_high = power_required(speed_mps, 0, rider, env_high)

        # ~18% less air density should noticeably reduce power
        assert power_high < power_sea

    def test_default_env_params(self, rider):
        """Should work with default environment params."""
        power = power_required(10.0, 0, rider)
        assert power > 0


# =============================================================================
# Test speed_from_power
# =============================================================================


class TestSpeedFromPower:
    """Tests for speed_from_power function (inverse of power_required)."""

    @pytest.fixture
    def rider(self) -> RiderParams:
        """Standard test rider."""
        return RiderParams(mass_kg=83, cda=0.32, crr=0.004)

    def test_zero_power_returns_zero(self, rider):
        """Zero power should return zero speed."""
        speed = speed_from_power(0, 0, rider)
        assert speed == 0.0

    def test_negative_power_returns_zero(self, rider):
        """Negative power should return zero."""
        speed = speed_from_power(-100, 0, rider)
        assert speed == 0.0

    def test_flat_200w(self, rider):
        """200W on flat should give ~34 km/h."""
        speed = speed_from_power(200, 0, rider)
        speed_kph = speed * 3.6
        assert 32 < speed_kph < 36

    def test_flat_300w(self, rider):
        """300W on flat should give ~40 km/h."""
        speed = speed_from_power(300, 0, rider)
        speed_kph = speed * 3.6
        assert 38 < speed_kph < 42

    def test_climb_slower(self, rider):
        """Same power on 5% climb should be much slower."""
        speed_flat = speed_from_power(200, 0, rider)
        speed_climb = speed_from_power(200, 5.0, rider)

        assert speed_climb < speed_flat * 0.5  # Much slower

    def test_steep_climb_very_slow(self, rider):
        """200W on 10% should give ~8-12 km/h for heavy rider."""
        speed = speed_from_power(200, 10.0, rider)
        speed_kph = speed * 3.6
        # 83kg rider at 200W on 10% grade is very slow
        assert 6 < speed_kph < 14

    def test_descent_faster(self, rider):
        """Same power on descent should be faster."""
        speed_flat = speed_from_power(200, 0, rider)
        speed_descent = speed_from_power(200, -5.0, rider)

        assert speed_descent > speed_flat

    def test_roundtrip_consistency(self, rider):
        """speed_from_power should be inverse of power_required."""
        original_power = 250
        speed = speed_from_power(original_power, 2.0, rider)
        recovered_power = power_required(speed, 2.0, rider)

        assert recovered_power == pytest.approx(original_power, rel=0.01)

    def test_roundtrip_various_grades(self, rider):
        """Roundtrip should work for various grades."""
        for grade in [-6, -3, 0, 3, 6, 10]:
            original_power = 220
            speed = speed_from_power(original_power, grade, rider)
            if speed > 0:  # Skip if power insufficient for grade
                recovered_power = power_required(speed, grade, rider)
                assert recovered_power == pytest.approx(original_power, rel=0.02)

    def test_altitude_effect(self, rider):
        """Higher altitude should allow faster speed at same power."""
        env_sea = EnvironmentParams(air_density=1.225)
        env_high = EnvironmentParams(air_density=1.0)

        speed_sea = speed_from_power(200, 0, rider, env_sea)
        speed_high = speed_from_power(200, 0, rider, env_high)

        assert speed_high > speed_sea

    def test_convergence(self, rider):
        """Should converge for reasonable inputs."""
        # Test edge cases that might cause convergence issues
        test_cases = [
            (50, 0),  # Low power, flat
            (400, 0),  # High power, flat
            (200, 12),  # Moderate power, steep climb
            (150, -10),  # Low power, steep descent
        ]

        for power, grade in test_cases:
            speed = speed_from_power(power, grade, rider)
            assert speed >= 0
            assert speed < 50  # Reasonable upper bound


# =============================================================================
# Test time_for_segment
# =============================================================================


class TestTimeForSegment:
    """Tests for time_for_segment function."""

    @pytest.fixture
    def rider(self) -> RiderParams:
        """Standard test rider."""
        return RiderParams(mass_kg=75, cda=0.30, crr=0.004)

    def test_zero_distance_returns_zero(self, rider):
        """Zero distance should return zero time."""
        time = time_for_segment(0, 0, 200, rider)
        assert time == 0.0

    def test_negative_distance_returns_zero(self, rider):
        """Negative distance should return zero."""
        time = time_for_segment(-1000, 0, 200, rider)
        assert time == 0.0

    def test_1km_flat_at_200w(self, rider):
        """1km flat at 200W should take ~100-120 seconds."""
        time = time_for_segment(1000, 0, 200, rider)
        # At ~33 km/h, 1km takes ~109 seconds
        assert 90 < time < 130

    def test_climb_takes_longer(self, rider):
        """Same segment with climb should take longer."""
        time_flat = time_for_segment(1000, 0, 200, rider)
        time_climb = time_for_segment(1000, 5.0, 200, rider)

        assert time_climb > time_flat

    def test_descent_is_faster(self, rider):
        """Descent should be faster than flat."""
        time_flat = time_for_segment(1000, 0, 200, rider)
        time_descent = time_for_segment(1000, -5.0, 200, rider)

        assert time_descent < time_flat

    def test_zero_power_infinite_time(self, rider):
        """Zero power should return infinite time."""
        time = time_for_segment(1000, 0, 0, rider)
        assert time == float("inf")


# =============================================================================
# Test FTP/CP Estimation
# =============================================================================


class TestFtpCpEstimation:
    """Tests for FTP <-> CP estimation functions."""

    def test_estimate_ftp_from_cp(self):
        """FTP estimate from CP should be approximately equal."""
        cp = 250
        ftp = estimate_ftp_from_cp(cp)
        # Conservative estimate: FTP ≈ CP
        assert ftp == pytest.approx(cp, rel=0.05)

    def test_estimate_cp_from_ftp(self):
        """CP estimate from FTP should be approximately equal."""
        ftp = 280
        cp = estimate_cp_from_ftp(ftp)
        # CP ≈ FTP for trained cyclists
        assert cp == pytest.approx(ftp, rel=0.05)

    def test_roundtrip(self):
        """Roundtrip FTP -> CP -> FTP should be consistent."""
        original_ftp = 300
        cp = estimate_cp_from_ftp(original_ftp)
        recovered_ftp = estimate_ftp_from_cp(cp)
        assert recovered_ftp == pytest.approx(original_ftp, rel=0.01)


# =============================================================================
# Integration Tests
# =============================================================================


class TestPhysicsIntegration:
    """Integration tests for physics calculations."""

    def test_typical_tt_scenario(self):
        """Test a typical time trial scenario."""
        # TT rider: 75kg, low CdA (0.22), smooth tires
        rider = RiderParams(mass_kg=75, cda=0.22, crr=0.003)

        # 40km flat TT at 350W
        distance = 40000
        power = 350

        speed = speed_from_power(power, 0, rider)
        time = time_for_segment(distance, 0, power, rider)

        # Should achieve ~45 km/h, taking ~53 minutes
        speed_kph = speed * 3.6
        time_min = time / 60

        assert 43 < speed_kph < 48
        assert 50 < time_min < 60

    def test_alpine_climb_scenario(self):
        """Test a long alpine climb scenario."""
        # Climber: 65kg, standard position
        rider = RiderParams(mass_kg=65, cda=0.35, crr=0.004)

        # 10km at 8% average, putting out 280W
        distance = 10000
        grade = 8.0
        power = 280

        speed = speed_from_power(power, grade, rider)
        time = time_for_segment(distance, grade, power, rider)

        # Should climb at ~14-16 km/h, taking ~40-45 minutes
        speed_kph = speed * 3.6
        time_min = time / 60

        assert 13 < speed_kph < 17
        assert 35 < time_min < 50

    def test_descent_scenario(self):
        """Test a descent with soft pedaling."""
        rider = RiderParams(mass_kg=80, cda=0.40, crr=0.004)

        # 5km descent at -6%, soft pedaling at 100W
        speed = speed_from_power(100, -6.0, rider)

        # Should achieve high speed due to gravity assist
        speed_kph = speed * 3.6
        assert speed_kph > 50  # Fast descent




# =============================================================================
# Test calculate_bearing
# =============================================================================


class TestCalculateBearing:
    """Tests for calculate_bearing function."""

    def test_due_north(self):
        """Point directly north should give bearing 0."""
        bearing = calculate_bearing(0, 0, 1, 0)
        assert bearing == pytest.approx(0.0, abs=0.1)

    def test_due_south(self):
        """Point directly south should give bearing 180."""
        bearing = calculate_bearing(1, 0, 0, 0)
        assert bearing == pytest.approx(180.0, abs=0.1)

    def test_due_east(self):
        """Point directly east should give bearing 90."""
        bearing = calculate_bearing(0, 0, 0, 1)
        assert bearing == pytest.approx(90.0, abs=0.1)

    def test_due_west(self):
        """Point directly west should give bearing 270."""
        bearing = calculate_bearing(0, 0, 0, -1)
        assert bearing == pytest.approx(270.0, abs=0.1)

    def test_northeast(self):
        """Point northeast should give bearing ~45."""
        bearing = calculate_bearing(0, 0, 1, 1)
        assert 40 < bearing < 50

    def test_southeast(self):
        """Point southeast should give bearing ~135."""
        bearing = calculate_bearing(0, 0, -1, 1)
        assert 130 < bearing < 140

    def test_southwest(self):
        """Point southwest should give bearing ~225."""
        bearing = calculate_bearing(0, 0, -1, -1)
        assert 220 < bearing < 230

    def test_northwest(self):
        """Point northwest should give bearing ~315."""
        bearing = calculate_bearing(0, 0, 1, -1)
        assert 310 < bearing < 320

    def test_same_point_returns_zero(self):
        """Same start and end point should return 0."""
        bearing = calculate_bearing(47.0, 8.0, 47.0, 8.0)
        assert bearing == 0.0

    def test_real_world_zurich_to_bern(self):
        """Test bearing from Zurich to Bern (roughly west-southwest)."""
        # Zurich: 47.3769, 8.5417
        # Bern: 46.9480, 7.4474
        bearing = calculate_bearing(47.3769, 8.5417, 46.9480, 7.4474)
        # Should be roughly 240-250 degrees (west-southwest)
        assert 235 < bearing < 255


# =============================================================================
# Test calculate_headwind
# =============================================================================


class TestCalculateHeadwind:
    """Tests for calculate_headwind function."""

    def test_direct_headwind(self):
        """Wind from same direction as travel should be full headwind."""
        # Wind from north (0°), traveling north (0°)
        headwind = calculate_headwind(10, 0, 0)
        assert headwind == pytest.approx(10.0, abs=0.1)

    def test_direct_tailwind(self):
        """Wind from opposite direction should be full tailwind (negative)."""
        # Wind from south (180°), traveling north (0°)
        headwind = calculate_headwind(10, 180, 0)
        assert headwind == pytest.approx(-10.0, abs=0.1)

    def test_crosswind_from_east(self):
        """Crosswind from 90° off course should give zero headwind."""
        # Wind from east (90°), traveling north (0°)
        headwind = calculate_headwind(10, 90, 0)
        assert headwind == pytest.approx(0.0, abs=0.1)

    def test_crosswind_from_west(self):
        """Crosswind from 270° off course should give zero headwind."""
        # Wind from west (270°), traveling north (0°)
        headwind = calculate_headwind(10, 270, 0)
        assert headwind == pytest.approx(0.0, abs=0.1)

    def test_quartering_headwind(self):
        """45° quartering headwind should give ~70% of wind speed."""
        # Wind from NE (45°), traveling north (0°)
        headwind = calculate_headwind(10, 45, 0)
        # cos(45°) ≈ 0.707
        assert headwind == pytest.approx(7.07, abs=0.1)

    def test_quartering_tailwind(self):
        """45° quartering tailwind should give ~-70% of wind speed."""
        # Wind from SW (225°), traveling north (0°)
        headwind = calculate_headwind(10, 225, 0)
        # cos(225° - 0°) = cos(225°) ≈ -0.707
        assert headwind == pytest.approx(-7.07, abs=0.1)

    def test_zero_wind_speed(self):
        """Zero wind speed should give zero headwind regardless of direction."""
        headwind = calculate_headwind(0, 90, 45)
        assert headwind == 0.0

    def test_traveling_east_wind_from_west(self):
        """Traveling east with wind from west should be tailwind."""
        # Wind from west (270°) means wind blows toward east
        # Traveling east (90°) means wind is behind you = tailwind
        headwind = calculate_headwind(10, 270, 90)
        assert headwind == pytest.approx(-10.0, abs=0.1)

    def test_traveling_south_wind_from_north(self):
        """Traveling south with wind from north should be tailwind."""
        # Wind from north (0°) means wind blows toward south
        # Traveling south (180°) means wind is behind you = tailwind
        headwind = calculate_headwind(10, 0, 180)
        assert headwind == pytest.approx(-10.0, abs=0.1)

    def test_symmetry_of_crosswind(self):
        """Crosswinds from left vs right should have same magnitude."""
        hw_left = calculate_headwind(10, 45, 0)
        hw_right = calculate_headwind(10, 315, 0)
        assert hw_left == pytest.approx(hw_right, abs=0.01)

    def test_typical_race_scenario(self):
        """Test a realistic race scenario with moderate wind."""
        # 15 km/h wind (4.17 m/s) from northwest (315°)
        # Course heading northeast (45°)
        # Angle between = 315 - 45 = 270° → cos(270°) = 0
        # Actually: wind from 315, heading 45 → pure crosswind
        wind_mps = 15 / 3.6  # ~4.17 m/s
        headwind = calculate_headwind(wind_mps, 315, 45)
        assert headwind == pytest.approx(0.0, abs=0.1)
