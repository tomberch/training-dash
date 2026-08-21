"""Tests for physics-based CdA/Crr calibration."""

from __future__ import annotations

import numpy as np
import pytest

from trainingdash.domain.physics_calibration import (
    CalibrationDataPoint,
    PhysicsCalibrationResult,
    aggregate_records_to_data_points,
    calibrate_from_data_points,
    predict_speed_from_power,
)


class TestPredictSpeedFromPower:
    """Tests for physics-based speed prediction."""

    def test_flat_terrain_prediction(self):
        """On flat terrain, speed increases with power."""
        speed_150w = predict_speed_from_power(
            power_w=150.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )
        speed_250w = predict_speed_from_power(
            power_w=250.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )

        assert speed_250w > speed_150w
        # At 250W on flat with standard values, should be ~30+ km/h
        assert speed_250w > 8.0  # > 28.8 km/h

    def test_climb_reduces_speed(self):
        """Climbing at same power reduces speed."""
        speed_flat = predict_speed_from_power(
            power_w=200.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )
        speed_climb = predict_speed_from_power(
            power_w=200.0,
            grade_pct=5.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )

        assert speed_climb < speed_flat
        # 5% climb at 200W should be ~4-5 m/s (14-18 km/h)
        assert 3.0 < speed_climb < 7.0

    def test_descent_increases_speed(self):
        """Descending at same power increases speed."""
        speed_flat = predict_speed_from_power(
            power_w=100.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )
        speed_descent = predict_speed_from_power(
            power_w=100.0,
            grade_pct=-3.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )

        assert speed_descent > speed_flat

    def test_zero_power_returns_zero(self):
        """Zero power returns zero speed."""
        speed = predict_speed_from_power(
            power_w=0.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.35,
            crr=0.005,
        )
        assert speed == 0.0

    def test_higher_mass_reduces_speed_on_climb(self):
        """Higher mass reduces speed on climbs."""
        speed_light = predict_speed_from_power(
            power_w=200.0,
            grade_pct=5.0,
            total_mass_kg=70.0,
            cda=0.35,
            crr=0.005,
        )
        speed_heavy = predict_speed_from_power(
            power_w=200.0,
            grade_pct=5.0,
            total_mass_kg=100.0,
            cda=0.35,
            crr=0.005,
        )

        assert speed_light > speed_heavy

    def test_higher_cda_reduces_speed_on_flat(self):
        """Higher CdA (less aero) reduces speed on flat terrain."""
        speed_aero = predict_speed_from_power(
            power_w=200.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.25,  # Aero position
            crr=0.005,
        )
        speed_upright = predict_speed_from_power(
            power_w=200.0,
            grade_pct=0.0,
            total_mass_kg=80.0,
            cda=0.45,  # Upright position
            crr=0.005,
        )

        assert speed_aero > speed_upright


class TestCalibrateFromDataPoints:
    """Tests for the physics-based calibration fitting."""

    def test_minimum_data_points_required(self):
        """Calibration needs at least 3 data points."""
        points = [
            CalibrationDataPoint(grade_pct=0.0, power_w=200.0, speed_mps=8.0),
            CalibrationDataPoint(grade_pct=5.0, power_w=200.0, speed_mps=4.5),
        ]

        with pytest.raises(ValueError, match="At least 3 data points"):
            calibrate_from_data_points(points, total_mass_kg=80.0)

    def test_calibration_with_synthetic_data(self):
        """Calibration recovers known CdA/Crr from synthetic data."""
        # Generate synthetic data with known parameters
        true_cda = 0.35
        true_crr = 0.005
        total_mass = 80.0

        grades = [0.0, 2.0, 5.0, 8.0, -2.0]
        powers = [200.0, 250.0, 280.0, 300.0, 100.0]

        points = []
        for grade, power in zip(grades, powers):
            speed = predict_speed_from_power(
                power_w=power,
                grade_pct=grade,
                total_mass_kg=total_mass,
                cda=true_cda,
                crr=true_crr,
            )
            points.append(
                CalibrationDataPoint(
                    grade_pct=grade,
                    power_w=power,
                    speed_mps=speed,
                    duration_s=60.0,
                )
            )

        result = calibrate_from_data_points(points, total_mass_kg=total_mass)

        # Should recover close to true values
        assert abs(result.cda - true_cda) < 0.05
        assert abs(result.crr - true_crr) < 0.002

    def test_result_has_diagnostics(self):
        """Calibration result includes diagnostic information."""
        points = [
            CalibrationDataPoint(grade_pct=0.0, power_w=200.0, speed_mps=8.0, duration_s=60.0),
            CalibrationDataPoint(grade_pct=3.0, power_w=220.0, speed_mps=5.5, duration_s=60.0),
            CalibrationDataPoint(grade_pct=6.0, power_w=250.0, speed_mps=4.0, duration_s=60.0),
            CalibrationDataPoint(grade_pct=-2.0, power_w=100.0, speed_mps=9.0, duration_s=60.0),
        ]

        result = calibrate_from_data_points(points, total_mass_kg=80.0)

        assert isinstance(result, PhysicsCalibrationResult)
        assert result.confidence in ("low", "medium", "high")
        assert result.n_data_points == 4
        assert result.rms_error_pct >= 0
        assert result.max_error_pct >= 0
        assert len(result.grade_range) == 2

    def test_steep_descents_filtered(self):
        """Steep descents (< -4%) are filtered out."""
        points = [
            CalibrationDataPoint(grade_pct=0.0, power_w=200.0, speed_mps=8.0, duration_s=60.0),
            CalibrationDataPoint(grade_pct=5.0, power_w=250.0, speed_mps=4.5, duration_s=60.0),
            CalibrationDataPoint(grade_pct=-6.0, power_w=50.0, speed_mps=15.0, duration_s=60.0),  # Filtered
            CalibrationDataPoint(grade_pct=3.0, power_w=220.0, speed_mps=5.5, duration_s=60.0),
        ]

        result = calibrate_from_data_points(points, total_mass_kg=80.0)

        # The -6% point should be filtered
        assert result.n_data_points == 3

    def test_cda_bounded(self):
        """CdA stays within reasonable bounds (0.20-0.65)."""
        # Extreme data that might push CdA out of bounds
        points = [
            CalibrationDataPoint(grade_pct=0.0, power_w=300.0, speed_mps=15.0, duration_s=60.0),
            CalibrationDataPoint(grade_pct=5.0, power_w=300.0, speed_mps=5.0, duration_s=60.0),
            CalibrationDataPoint(grade_pct=10.0, power_w=300.0, speed_mps=3.0, duration_s=60.0),
        ]

        result = calibrate_from_data_points(points, total_mass_kg=80.0)

        assert 0.20 <= result.cda <= 0.65
        assert 0.002 <= result.crr <= 0.012


class TestAggregateRecordsToDataPoints:
    """Tests for aggregating time-series data into calibration points."""

    def test_groups_by_grade_bins(self):
        """Records are grouped into 1% grade bins."""
        np.random.seed(42)
        n = 200

        # Create data with grades 0%, 3%, 5%
        power = np.array([200.0] * n)
        speed = np.array([8.0] * 60 + [5.0] * 70 + [4.0] * 70)
        grade = np.array([0.0] * 60 + [3.0] * 70 + [5.0] * 70)
        timestamps = np.arange(n, dtype=float)

        points = aggregate_records_to_data_points(power, speed, grade, timestamps)

        # Should have 3 grade bins
        assert len(points) == 3
        grade_bins = sorted(p.grade_pct for p in points)
        assert grade_bins == [0.0, 3.0, 5.0]

    def test_requires_minimum_samples_per_bin(self):
        """Each grade bin needs at least 30 samples."""
        n = 50
        power = np.array([200.0] * n)
        speed = np.array([8.0] * 25 + [5.0] * 25)
        grade = np.array([0.0] * 25 + [5.0] * 25)  # Only 25 samples per bin
        timestamps = np.arange(n, dtype=float)

        points = aggregate_records_to_data_points(power, speed, grade, timestamps)

        # Should have 0 bins (neither has 30 samples)
        assert len(points) == 0

    def test_filters_low_power(self):
        """Samples with power < 30W are excluded."""
        n = 120
        power = np.array([10.0] * 60 + [200.0] * 60)  # First 60 too low
        speed = np.array([8.0] * n)
        grade = np.array([0.0] * n)
        timestamps = np.arange(n, dtype=float)

        points = aggregate_records_to_data_points(power, speed, grade, timestamps)

        # Should have 1 bin from the 60 valid samples
        assert len(points) == 1
        # Duration should reflect 60 samples, not 120
        assert points[0].duration_s == 60.0

    def test_filters_low_speed(self):
        """Samples with speed < 1.5 m/s are excluded."""
        n = 120
        power = np.array([200.0] * n)
        speed = np.array([0.5] * 60 + [8.0] * 60)  # First 60 too slow
        grade = np.array([0.0] * n)
        timestamps = np.arange(n, dtype=float)

        points = aggregate_records_to_data_points(power, speed, grade, timestamps)

        # Should have 1 bin from the 60 valid samples
        assert len(points) == 1

    def test_insufficient_data_returns_empty(self):
        """Returns empty list if too few records."""
        power = np.array([200.0] * 10)
        speed = np.array([8.0] * 10)
        grade = np.array([0.0] * 10)
        timestamps = np.arange(10, dtype=float)

        points = aggregate_records_to_data_points(
            power, speed, grade, timestamps, window_size=60
        )

        assert len(points) == 0
