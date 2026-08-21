"""Unit tests for CdA estimation module."""

import numpy as np
import pytest

from trainingdash.domain.calibration_segments import CalibrationSegment
from trainingdash.domain.cda_estimation import (
    CalibrationInput,
    CdAEstimate,
    confidence_tier,
    estimate_cda,
    get_default_cda,
    get_default_crr,
    inputs_from_segments,
)

# =============================================================================
# Test CalibrationInput
# =============================================================================


class TestCalibrationInput:
    """Tests for CalibrationInput dataclass."""

    def test_duration_from_power_length(self):
        """Duration should equal number of power samples (1Hz assumption)."""
        inp = CalibrationInput(
            power=(200, 210, 205, 208, 202),
            speed=(10.0, 10.1, 10.0, 9.9, 10.0),
            grade=(0.5, 0.5, 0.5, 0.5, 0.5),
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )
        assert inp.duration_s == 5.0

    def test_mean_power_calculation(self):
        """Mean power should be calculated correctly."""
        inp = CalibrationInput(
            power=(200, 220, 210),
            speed=(10.0, 10.0, 10.0),
            grade=(0.0, 0.0, 0.0),
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )
        assert inp.mean_power == pytest.approx(210.0)

    def test_mean_speed_calculation(self):
        """Mean speed should be calculated correctly."""
        inp = CalibrationInput(
            power=(200, 200, 200),
            speed=(9.0, 10.0, 11.0),
            grade=(0.0, 0.0, 0.0),
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )
        assert inp.mean_speed == pytest.approx(10.0)

    def test_mean_grade_calculation(self):
        """Mean grade should be calculated correctly."""
        inp = CalibrationInput(
            power=(200, 200, 200),
            speed=(10.0, 10.0, 10.0),
            grade=(-1.0, 0.0, 1.0),
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )
        assert inp.mean_grade == pytest.approx(0.0)

    def test_empty_power_returns_zero_mean(self):
        """Empty power array should return zero mean."""
        inp = CalibrationInput(
            power=(),
            speed=(),
            grade=(),
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )
        assert inp.mean_power == 0.0
        assert inp.mean_speed == 0.0
        assert inp.duration_s == 0.0


# =============================================================================
# Test estimate_cda
# =============================================================================


class TestEstimateCda:
    """Tests for CdA estimation function."""

    def test_basic_estimation(self):
        """Should estimate CdA from valid calibration inputs."""
        # Create inputs with known characteristics
        # At ~36 km/h (10 m/s), flat road, 250W, ~80kg
        # CdA ≈ (P × η / v - m × g × Crr) / (0.5 × ρ × v²)
        inputs = [
            CalibrationInput(
                power=tuple([250.0] * 30),
                speed=tuple([10.0] * 30),
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
        ]

        result = estimate_cda(inputs)

        assert isinstance(result, CdAEstimate)
        # CdA should be in reasonable range (0.2 - 0.5 for road bikes)
        assert 0.15 < result.cda < 0.50
        assert result.n_segments == 1

    def test_multiple_segments_improves_estimate(self):
        """Multiple consistent segments should improve confidence."""
        # Create multiple consistent inputs
        inputs = [
            CalibrationInput(
                power=tuple([250.0] * 60),
                speed=tuple([10.0] * 60),
                grade=tuple([0.0] * 60),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
            for _ in range(5)
        ]

        result = estimate_cda(inputs)

        assert result.n_segments == 5
        assert result.total_duration_s == 300.0

    def test_empty_inputs_raises(self):
        """Empty inputs should raise ValueError."""
        with pytest.raises(ValueError, match="No calibration inputs"):
            estimate_cda([])

    def test_zero_speed_segment_ignored(self):
        """Segments with zero speed should be ignored."""
        inputs = [
            CalibrationInput(
                power=tuple([0.0] * 30),
                speed=tuple([0.0] * 30),  # Zero speed
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            ),
            CalibrationInput(
                power=tuple([250.0] * 30),
                speed=tuple([10.0] * 30),  # Valid
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            ),
        ]

        result = estimate_cda(inputs)

        # Only valid segment should be used
        assert result.n_segments == 1

    def test_fixed_crr(self):
        """Should accept fixed Crr value."""
        inputs = [
            CalibrationInput(
                power=tuple([250.0] * 30),
                speed=tuple([10.0] * 30),
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.005,  # This value
            )
        ]

        # Use different fixed Crr
        result = estimate_cda(inputs, crr_fixed=0.003)

        # Should still produce valid estimate
        assert 0.1 < result.cda < 0.6

    def test_returns_default_when_all_invalid(self):
        """Returns default CdA with low confidence when all segments invalid."""
        inputs = [
            CalibrationInput(
                power=tuple([0.0] * 30),
                speed=tuple([0.0] * 30),
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
        ]

        result = estimate_cda(inputs)

        assert result.cda == 0.32  # Default
        assert result.confidence == "low"
        assert result.n_segments == 0


class TestCdaEstimateResult:
    """Tests for CdAEstimate result structure."""

    def test_result_has_all_fields(self):
        """Result should contain all expected fields."""
        inputs = [
            CalibrationInput(
                power=tuple([250.0] * 60),
                speed=tuple([10.0] * 60),
                grade=tuple([0.0] * 60),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
        ]

        result = estimate_cda(inputs)

        assert hasattr(result, "cda")
        assert hasattr(result, "confidence")
        assert hasattr(result, "std_error")
        assert hasattr(result, "r_squared")
        assert hasattr(result, "n_segments")
        assert hasattr(result, "total_duration_s")
        assert hasattr(result, "estimates_by_segment")

    def test_estimates_by_segment_length(self):
        """Should have one estimate per valid segment."""
        inputs = [
            CalibrationInput(
                power=tuple([250.0] * 30),
                speed=tuple([10.0] * 30),
                grade=tuple([0.0] * 30),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
            for _ in range(3)
        ]

        result = estimate_cda(inputs)

        assert len(result.estimates_by_segment) == 3


# =============================================================================
# Test confidence_tier
# =============================================================================


class TestConfidenceTier:
    """Tests for confidence tier determination."""

    def test_high_confidence(self):
        """High confidence: >= 5 segments, >= 300s, CV < 3%."""
        tier = confidence_tier(n_segments=5, total_duration_s=300, cv=0.02)
        assert tier == "high"

    def test_medium_confidence(self):
        """Medium confidence: >= 3 segments, >= 120s, CV < 5%."""
        tier = confidence_tier(n_segments=3, total_duration_s=120, cv=0.04)
        assert tier == "medium"

    def test_low_confidence_few_segments(self):
        """Low confidence with too few segments."""
        tier = confidence_tier(n_segments=2, total_duration_s=300, cv=0.02)
        assert tier == "low"

    def test_low_confidence_short_duration(self):
        """Low confidence with too short duration."""
        tier = confidence_tier(n_segments=5, total_duration_s=100, cv=0.02)
        assert tier == "low"

    def test_low_confidence_high_cv(self):
        """Low confidence with high coefficient of variation."""
        tier = confidence_tier(n_segments=5, total_duration_s=300, cv=0.10)
        assert tier == "low"

    def test_medium_when_not_high(self):
        """Medium confidence when high criteria not met but medium met."""
        # 4 segments (< 5 for high), but meets medium criteria
        tier = confidence_tier(n_segments=4, total_duration_s=200, cv=0.04)
        assert tier == "medium"


# =============================================================================
# Test Default Values
# =============================================================================


class TestDefaultValues:
    """Tests for default CdA and Crr values."""

    def test_get_default_cda_road(self):
        """Road bike default CdA should be reasonable."""
        cda = get_default_cda("road")
        assert 0.25 < cda < 0.40

    def test_get_default_cda_tt(self):
        """TT bike default CdA should be lower than road."""
        tt_cda = get_default_cda("tt")
        road_cda = get_default_cda("road")
        assert tt_cda < road_cda

    def test_get_default_crr_road(self):
        """Road bike default Crr should be reasonable."""
        crr = get_default_crr("road")
        assert 0.002 < crr < 0.006

    def test_get_default_crr_gravel(self):
        """Gravel bike default Crr should be higher than road."""
        gravel_crr = get_default_crr("gravel")
        road_crr = get_default_crr("road")
        assert gravel_crr > road_crr

    def test_invalid_bike_type_raises(self):
        """Invalid bike type should raise KeyError."""
        with pytest.raises(KeyError):
            get_default_cda("unknown_type")


# =============================================================================
# Test inputs_from_segments
# =============================================================================


class TestInputsFromSegments:
    """Tests for inputs_from_segments helper."""

    def test_creates_inputs_for_each_segment(self):
        """Should create one CalibrationInput per segment."""
        segments = [
            CalibrationSegment(
                start_idx=0,
                end_idx=30,
                duration_s=30,
                mean_speed_mps=10.0,
                mean_power_w=250.0,
                mean_grade_pct=0.0,
                power_cv=0.05,
                speed_cv=0.02,
                quality_score=0.9,
            ),
            CalibrationSegment(
                start_idx=40,
                end_idx=70,
                duration_s=30,
                mean_speed_mps=11.0,
                mean_power_w=270.0,
                mean_grade_pct=0.5,
                power_cv=0.04,
                speed_cv=0.02,
                quality_score=0.85,
            ),
        ]

        # Create mock arrays
        power = np.array([250.0] * 100)
        speed = np.array([10.0] * 100)
        grade = np.array([0.0] * 100)

        inputs = inputs_from_segments(
            segments=segments,
            power=power,
            speed=speed,
            grade=grade,
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )

        assert len(inputs) == 2
        assert all(isinstance(inp, CalibrationInput) for inp in inputs)

    def test_slices_arrays_correctly(self):
        """Should slice arrays to segment boundaries."""
        segments = [
            CalibrationSegment(
                start_idx=10,
                end_idx=20,
                duration_s=10,
                mean_speed_mps=10.0,
                mean_power_w=250.0,
                mean_grade_pct=0.0,
                power_cv=0.05,
                speed_cv=0.02,
                quality_score=0.9,
            ),
        ]

        # Create arrays with distinct values to verify slicing
        power = np.arange(100, dtype=float)  # 0, 1, 2, ...
        speed = np.arange(100, dtype=float) / 10  # 0, 0.1, 0.2, ...
        grade = np.zeros(100)

        inputs = inputs_from_segments(
            segments=segments,
            power=power,
            speed=speed,
            grade=grade,
            air_density=1.225,
            rider_mass=80,
            crr=0.004,
        )

        assert len(inputs) == 1
        # Power should be sliced from index 10 to 20
        assert len(inputs[0].power) == 10
        assert inputs[0].power[0] == 10.0  # First value at index 10


# =============================================================================
# Integration Tests
# =============================================================================


class TestCdaEstimationIntegration:
    """Integration tests for realistic scenarios."""

    def test_typical_road_bike_estimation(self):
        """Estimate CdA for typical road bike scenario."""
        # Rider at 36 km/h (10 m/s), 250W, flat road
        # Expected CdA around 0.30-0.35 for road position
        inputs = [
            CalibrationInput(
                power=tuple([250.0 + np.random.normal(0, 5) for _ in range(60)]),
                speed=tuple([10.0 + np.random.normal(0, 0.2) for _ in range(60)]),
                grade=tuple([0.0] * 60),
                air_density=1.225,
                rider_mass=80,
                crr=0.004,
            )
            for _ in range(5)
        ]

        result = estimate_cda(inputs)

        # Should be in reasonable range for road bike
        assert 0.20 < result.cda < 0.45
        assert result.confidence in ("medium", "high")

    def test_high_speed_estimation(self):
        """CdA estimation at high speed (more aero dominated)."""
        # At higher speed, aero drag dominates, making CdA estimation more reliable
        inputs = [
            CalibrationInput(
                power=tuple([350.0] * 60),  # Higher power
                speed=tuple([12.0] * 60),  # ~43 km/h
                grade=tuple([0.0] * 60),
                air_density=1.225,
                rider_mass=75,
                crr=0.004,
            )
            for _ in range(5)
        ]

        result = estimate_cda(inputs)

        # Should produce a valid estimate
        assert 0.15 < result.cda < 0.50
