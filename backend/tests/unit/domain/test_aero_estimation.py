"""Unit tests for wind-corrected CdA/Crr estimation."""

import pytest

from trainingdash.domain.aero_estimation import (
    ActivityRecord,
    WeatherSnapshot,
    WindCorrectedDataPoint,
    calculate_air_density,
    calculate_headwind_component,
    calculate_rider_heading,
    check_estimation_requirements,
    estimate_cda_crr,
    interpolate_weather,
    prepare_data_points,
)


class TestCalculateAirDensity:
    """Tests for air density calculation."""

    def test_sea_level_standard_conditions(self):
        """ISA standard conditions: 15°C, 1013.25 hPa, 0% humidity."""
        rho = calculate_air_density(15.0, 1013.25, 0.0)
        # ISA standard is 1.225 kg/m³
        assert 1.22 < rho < 1.23

    def test_higher_temperature_lower_density(self):
        """Higher temperature = lower air density."""
        rho_cold = calculate_air_density(0.0, 1013.25, 50.0)
        rho_hot = calculate_air_density(35.0, 1013.25, 50.0)
        assert rho_hot < rho_cold

    def test_lower_pressure_lower_density(self):
        """Lower pressure = lower air density (altitude effect)."""
        rho_sea = calculate_air_density(20.0, 1013.25, 50.0)
        rho_mountain = calculate_air_density(20.0, 850.0, 50.0)  # ~1500m altitude
        assert rho_mountain < rho_sea

    def test_higher_humidity_lower_density(self):
        """Higher humidity = slightly lower air density (water vapor is lighter)."""
        rho_dry = calculate_air_density(25.0, 1013.25, 0.0)
        rho_humid = calculate_air_density(25.0, 1013.25, 100.0)
        assert rho_humid < rho_dry

    def test_typical_summer_ride(self):
        """Typical summer conditions: 25°C, 1010 hPa, 60% humidity."""
        rho = calculate_air_density(25.0, 1010.0, 60.0)
        # Should be around 1.16-1.18 kg/m³
        assert 1.15 < rho < 1.20


class TestCalculateRiderHeading:
    """Tests for rider heading calculation from GPS."""

    def test_heading_north(self):
        """Moving north = heading ~0°."""
        heading = calculate_rider_heading(47.0, 8.0, 47.1, 8.0)
        assert heading > 355 or heading < 5

    def test_heading_east(self):
        """Moving east = heading ~90°."""
        heading = calculate_rider_heading(47.0, 8.0, 47.0, 8.1)
        assert 85 < heading < 95

    def test_heading_south(self):
        """Moving south = heading ~180°."""
        heading = calculate_rider_heading(47.1, 8.0, 47.0, 8.0)
        assert 175 < heading < 185

    def test_heading_west(self):
        """Moving west = heading ~270°."""
        heading = calculate_rider_heading(47.0, 8.1, 47.0, 8.0)
        assert 265 < heading < 275

    def test_heading_northeast(self):
        """Moving northeast = heading ~45° (depends on latitude)."""
        heading = calculate_rider_heading(47.0, 8.0, 47.1, 8.1)
        # At 47° latitude, 1° lon ≈ 0.68 × 1° lat, so actual heading will be less than 45°
        assert 30 < heading < 50


class TestCalculateHeadwindComponent:
    """Tests for headwind component calculation."""

    def test_pure_headwind(self):
        """Wind directly opposing rider = full headwind."""
        # Rider heading north (0°), wind from north (0°) = headwind
        headwind = calculate_headwind_component(0, 0, 5.0)
        assert headwind > 4.9  # Should be ~5 m/s headwind

    def test_pure_tailwind(self):
        """Wind directly behind rider = negative (tailwind)."""
        # Rider heading north (0°), wind from south (180°) = tailwind
        headwind = calculate_headwind_component(0, 180, 5.0)
        assert headwind < -4.9  # Should be ~-5 m/s (tailwind)

    def test_crosswind(self):
        """Wind perpendicular to rider = zero headwind component."""
        # Rider heading north (0°), wind from east (90°) = crosswind
        headwind = calculate_headwind_component(0, 90, 5.0)
        assert abs(headwind) < 0.1  # Should be ~0

    def test_quartering_headwind(self):
        """Wind at 45° angle = partial headwind."""
        # Rider heading north, wind from northeast
        headwind = calculate_headwind_component(0, 45, 5.0)
        # cos(45°) ≈ 0.707, so headwind should be ~3.5 m/s
        assert 3.0 < headwind < 4.0

    def test_rider_heading_east_wind_from_west(self):
        """Rider heading east, wind from west = tailwind (west wind pushes east)."""
        # Wind from west (270°) means wind blows TO the east
        # Rider heading east (90°) gets a tailwind
        headwind = calculate_headwind_component(90, 270, 10.0)
        assert headwind < -9.9  # Tailwind (negative)


class TestInterpolateWeather:
    """Tests for weather interpolation between hourly snapshots."""

    @pytest.fixture
    def weather_snapshots(self):
        return [
            WeatherSnapshot(
                hour_offset=0,
                wind_speed_mps=5.0,
                wind_direction_deg=90.0,
                pressure_hpa=1010.0,
                humidity_pct=60.0,
                temperature_c=20.0,
            ),
            WeatherSnapshot(
                hour_offset=1,
                wind_speed_mps=10.0,
                wind_direction_deg=180.0,
                pressure_hpa=1008.0,
                humidity_pct=70.0,
                temperature_c=22.0,
            ),
        ]

    def test_interpolate_at_hour_boundary(self, weather_snapshots):
        """At exact hour boundary, return that hour's data."""
        result = interpolate_weather(0.0, weather_snapshots)
        assert result.wind_speed_mps == 5.0
        assert result.temperature_c == 20.0

    def test_interpolate_midpoint(self, weather_snapshots):
        """At midpoint (30 min), interpolate linearly."""
        result = interpolate_weather(1800.0, weather_snapshots)  # 30 minutes = 0.5 hours
        assert result.wind_speed_mps == 7.5  # (5 + 10) / 2
        assert result.temperature_c == 21.0  # (20 + 22) / 2
        assert result.pressure_hpa == 1009.0

    def test_interpolate_wind_direction_wraparound(self):
        """Wind direction interpolation handles 360/0 wraparound."""
        snapshots = [
            WeatherSnapshot(0, 5.0, 350.0, 1010.0, 50.0, 20.0),
            WeatherSnapshot(1, 5.0, 10.0, 1010.0, 50.0, 20.0),
        ]
        result = interpolate_weather(1800.0, snapshots)
        # Should interpolate through 0, not through 180
        assert result.wind_direction_deg == 0.0 or abs(result.wind_direction_deg - 360) < 1

    def test_before_first_snapshot(self):
        """Before first snapshot, use first snapshot."""
        snapshots = [
            WeatherSnapshot(1, 5.0, 90.0, 1010.0, 50.0, 20.0),
        ]
        result = interpolate_weather(0.0, snapshots)
        assert result.wind_speed_mps == 5.0

    def test_empty_snapshots(self):
        """Empty snapshots returns None."""
        result = interpolate_weather(1800.0, [])
        assert result is None


class TestCheckEstimationRequirements:
    """Tests for estimation eligibility checking."""

    def test_measured_power_required(self):
        """Must have measured power, not HR-derived."""
        records = [
            ActivityRecord(i * 1.0, 47.0 + i * 0.0001, 8.0, 200, 8.0, 500.0, 20, None)
            for i in range(1500)  # 25 minutes
        ]
        can_estimate, reasons = check_estimation_requirements(records, "hr_derived")
        assert not can_estimate
        assert any("measured" in r for r in reasons)

    def test_duration_requirement(self):
        """Must be at least 20 minutes."""
        records = [
            ActivityRecord(i * 1.0, 47.0 + i * 0.0001, 8.0, 200, 8.0, 500.0, 20, None)
            for i in range(600)  # 10 minutes
        ]
        can_estimate, reasons = check_estimation_requirements(records, "measured")
        assert not can_estimate
        assert any("Duration" in r for r in reasons)

    def test_gps_coverage_requirement(self):
        """Must have at least 50% GPS coverage."""
        records = [ActivityRecord(i * 1.0, None, None, 200, 8.0, 500.0, 20, None) for i in range(1500)]
        can_estimate, reasons = check_estimation_requirements(records, "measured")
        assert not can_estimate
        assert any("GPS" in r for r in reasons)

    def test_power_coverage_requirement(self):
        """Must have at least 50% power coverage."""
        records = [ActivityRecord(i * 1.0, 47.0 + i * 0.0001, 8.0, None, 8.0, 500.0, 20, None) for i in range(1500)]
        can_estimate, reasons = check_estimation_requirements(records, "measured")
        assert not can_estimate
        assert any("Power coverage" in r for r in reasons)

    def test_valid_activity_passes(self):
        """Valid activity with all requirements met passes."""
        records = [
            ActivityRecord(i * 1.0, 47.0 + i * 0.0001, 8.0, 200, 8.0, 500.0 + i * 0.1, 20, None)
            for i in range(1500)  # 25 minutes
        ]
        can_estimate, reasons = check_estimation_requirements(records, "measured")
        assert can_estimate
        assert len(reasons) == 0


class TestEstimateCdaCrr:
    """Tests for the main CdA/Crr estimation function."""

    def _make_data_points(
        self,
        n_points: int = 100,
        base_grade: float = 0.0,
        grade_variation: float = 5.0,
    ) -> list[WindCorrectedDataPoint]:
        """Generate synthetic data points for testing."""
        # Simulate a 75kg rider + 9kg bike at ~200W
        # With CdA=0.32, Crr=0.005
        points = []
        for i in range(n_points):
            grade = base_grade + (i % 10 - 5) * (grade_variation / 5)
            # Simple physics approximation
            speed = 8.0 - grade * 0.5  # Slower uphill
            power = 180 + grade * 10  # More power uphill

            points.append(
                WindCorrectedDataPoint(
                    grade_pct=grade,
                    power_w=power,
                    ground_speed_mps=max(2.0, speed),
                    apparent_speed_mps=max(2.0, speed + 1.0),  # Slight headwind
                    air_density=1.2,
                    duration_s=1.0,
                )
            )
        return points

    def test_insufficient_data_points(self):
        """Should fail gracefully with too few points."""
        points = self._make_data_points(n_points=5)
        result = estimate_cda_crr(points, total_mass_kg=84.0)
        assert result.confidence == 0.0
        assert "Insufficient" in result.warnings[0]

    def test_estimation_produces_reasonable_values(self):
        """Estimation should produce values in reasonable range."""
        points = self._make_data_points(n_points=500, grade_variation=8.0)
        result = estimate_cda_crr(points, total_mass_kg=84.0)

        # CdA should be in reasonable range (0.20 - 0.60)
        assert 0.20 <= result.cda <= 0.60
        # Crr should be in reasonable range (0.002 - 0.012)
        assert 0.002 <= result.crr <= 0.012
        # Should have some confidence
        assert result.confidence > 0

    def test_limited_grade_range_warning(self):
        """Should warn when grade range is too narrow."""
        points = self._make_data_points(n_points=100, grade_variation=1.0)
        result = estimate_cda_crr(points, total_mass_kg=84.0)
        assert any("grade range" in w.lower() for w in result.warnings)

    def test_confidence_increases_with_more_data(self):
        """More data points should give higher confidence."""
        points_small = self._make_data_points(n_points=50, grade_variation=6.0)
        points_large = self._make_data_points(n_points=500, grade_variation=6.0)

        result_small = estimate_cda_crr(points_small, total_mass_kg=84.0)
        result_large = estimate_cda_crr(points_large, total_mass_kg=84.0)

        assert result_large.confidence >= result_small.confidence

    def test_confidence_decreases_with_low_weather_coverage(self):
        """Low weather coverage should reduce confidence."""
        points = self._make_data_points(n_points=500, grade_variation=6.0)

        result_full = estimate_cda_crr(points, total_mass_kg=84.0, weather_coverage_pct=100.0)
        result_partial = estimate_cda_crr(points, total_mass_kg=84.0, weather_coverage_pct=50.0)
        result_none = estimate_cda_crr(points, total_mass_kg=84.0, weather_coverage_pct=0.0)

        # Confidence should decrease with lower weather coverage
        assert result_full.confidence >= result_partial.confidence
        assert result_partial.confidence >= result_none.confidence


class TestPrepareDataPoints:
    """Tests for converting activity records to calibration data points."""

    def test_filters_low_power(self):
        """Should filter out records with power < 30W."""
        records = [
            ActivityRecord(0.0, 47.0, 8.0, 200, 8.0, 500.0, 20, None),
            ActivityRecord(1.0, 47.0001, 8.0001, 10, 8.0, 500.0, 20, None),  # Low power
            ActivityRecord(2.0, 47.0002, 8.0002, 200, 8.0, 500.0, 20, None),
        ]
        weather = [WeatherSnapshot(0, 5.0, 90.0, 1010.0, 50.0, 20.0)]

        points, _data_quality, warnings = prepare_data_points(records, weather)
        # Should have fewer points due to filtering
        assert len(points) <= 2

    def test_filters_low_speed(self):
        """Should filter out records with speed < 1.0 m/s."""
        records = [
            ActivityRecord(0.0, 47.0, 8.0, 200, 8.0, 500.0, 20, None),
            ActivityRecord(1.0, 47.0001, 8.0001, 200, 0.5, 500.0, 20, None),  # Low speed
            ActivityRecord(2.0, 47.0002, 8.0002, 200, 8.0, 500.0, 20, None),
        ]
        weather = [WeatherSnapshot(0, 5.0, 90.0, 1010.0, 50.0, 20.0)]

        points, _data_quality, warnings = prepare_data_points(records, weather)
        assert len(points) <= 2

    def test_uses_fit_temperature_over_weather(self):
        """Should prefer FIT file temperature for air density calculation."""
        records = [
            ActivityRecord(0.0, 47.0, 8.0, 200, 8.0, 500.0, 30, None),  # FIT temp = 30°C
            ActivityRecord(1.0, 47.0001, 8.0001, 200, 8.0, 501.0, 30, None),
        ]
        weather = [WeatherSnapshot(0, 5.0, 90.0, 1010.0, 50.0, 15.0)]  # Weather temp = 15°C

        points, _data_quality, warnings = prepare_data_points(records, weather)

        if points:
            # Air density at 30°C is lower than at 15°C
            # At 1010 hPa, 50% humidity:
            # 30°C → ~1.15 kg/m³, 15°C → ~1.22 kg/m³
            assert points[0].air_density < 1.20

    def test_warns_on_missing_weather(self):
        """Should warn when no weather data available."""
        records = [
            ActivityRecord(0.0, 47.0, 8.0, 200, 8.0, 500.0, 20, None),
            ActivityRecord(1.0, 47.0001, 8.0001, 200, 8.0, 501.0, 20, None),
        ]

        points, data_quality, warnings = prepare_data_points(records, [])
        assert any("weather" in w.lower() for w in warnings)
        assert data_quality.weather_coverage_pct == 0.0
