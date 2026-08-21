"""Tests for CdA estimation (domain/cda_estimation.py).

Tests cover:
- CdAEstimate and CalibrationInput dataclasses
- Single segment CdA estimation
- Multi-segment weighted estimation
- Confidence tier determination
- Default Crr values
"""

import numpy as np
import pytest

from trainingdash.domain.cda_estimation import (
    CdAEstimate,
    CalibrationInput,
    estimate_cda,
    _estimate_cda_single_segment,
    confidence_tier,
    get_default_crr,
    get_default_cda,
    inputs_from_segments,
)
from trainingdash.domain.calibration_segments import CalibrationSegment


class TestCalibrationInput:
    """Tests for CalibrationInput dataclass."""

    def test_create_input(self):
        """Should create a valid calibration input with arrays."""
        inp = CalibrationInput(
            power=(250.0, 251.0, 249.0),
            speed=(11.0, 11.1, 10.9),
            grade=(0.0, 0.1, -0.1),
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        assert inp.power == (250.0, 251.0, 249.0)
        assert inp.speed == (11.0, 11.1, 10.9)
        assert inp.duration_s == 3.0  # Length of arrays

    def test_mean_properties(self):
        """Should calculate mean values from arrays."""
        inp = CalibrationInput(
            power=(250.0, 260.0, 240.0),
            speed=(11.0, 12.0, 10.0),
            grade=(0.0, 1.0, -1.0),
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        assert inp.mean_power == 250.0
        assert inp.mean_speed == 11.0
        assert inp.mean_grade == 0.0


class TestSingleSegmentEstimation:
    """Tests for _estimate_cda_single_segment function."""

    def _make_input(self, power: float, speed: float, grade: float = 0.0, n_samples: int = 100) -> CalibrationInput:
        """Create a CalibrationInput with repeated values."""
        return CalibrationInput(
            power=tuple([power] * n_samples),
            speed=tuple([speed] * n_samples),
            grade=tuple([grade] * n_samples),
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )

    def test_zero_speed_returns_zero(self):
        """Zero speed should return zero CdA."""
        inp = self._make_input(power=250.0, speed=0.0)
        assert _estimate_cda_single_segment(inp) == 0.0

    def test_reasonable_cda_estimate(self):
        """Should estimate reasonable CdA from synthetic data."""
        # Create input matching a known CdA
        # At 40 km/h (11.11 m/s) flat, with CdA=0.32, power ~315W
        inp = self._make_input(power=315.0, speed=11.11)
        cda = _estimate_cda_single_segment(inp)
        
        # Should be close to 0.32
        assert 0.28 < cda < 0.36

    def test_higher_power_higher_cda(self):
        """Higher power at same speed implies higher CdA."""
        inp_low = self._make_input(power=250.0, speed=11.0)
        inp_high = self._make_input(power=350.0, speed=11.0)
        
        cda_low = _estimate_cda_single_segment(inp_low)
        cda_high = _estimate_cda_single_segment(inp_high)
        
        assert cda_high > cda_low

    def test_accounts_for_grade(self):
        """Should account for grade in estimation."""
        # On a climb, same power at same speed implies lower CdA
        # (more power goes to gravity)
        inp_flat = self._make_input(power=300.0, speed=10.0, grade=0.0)
        inp_climb = self._make_input(power=300.0, speed=10.0, grade=1.0)
        
        cda_flat = _estimate_cda_single_segment(inp_flat)
        cda_climb = _estimate_cda_single_segment(inp_climb)
        
        # On climb, less power available for aero → lower CdA estimate
        assert cda_climb < cda_flat


class TestEstimateCda:
    """Tests for estimate_cda function."""

    def _make_input(self, power: float, speed: float, grade: float = 0.0, n_samples: int = 100) -> CalibrationInput:
        """Create a CalibrationInput with repeated values."""
        return CalibrationInput(
            power=tuple([power] * n_samples),
            speed=tuple([speed] * n_samples),
            grade=tuple([grade] * n_samples),
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )

    def test_empty_inputs_raises(self):
        """Empty inputs should raise ValueError."""
        with pytest.raises(ValueError, match="No calibration inputs"):
            estimate_cda([])

    def test_single_segment_estimation(self):
        """Should estimate CdA from single segment."""
        inp = self._make_input(power=315.0, speed=11.11, n_samples=120)
        
        result = estimate_cda([inp])
        
        assert isinstance(result, CdAEstimate)
        assert 0.1 < result.cda < 0.8
        assert result.n_segments == 1
        assert result.confidence in ("low", "medium", "high")

    def test_multiple_segments_averaged(self):
        """Should average CdA across multiple segments."""
        inputs = [
            self._make_input(power=315.0, speed=11.11, n_samples=100),
            self._make_input(power=280.0, speed=10.5, n_samples=100),
            self._make_input(power=350.0, speed=11.5, n_samples=100),
        ]
        
        result = estimate_cda(inputs)
        
        assert result.n_segments == 3
        assert result.total_duration_s == 300.0
        assert len(result.estimates_by_segment) == 3

    def test_duration_weighted_averaging(self):
        """Longer segments should have more weight."""
        # Short segment with different CdA
        short_inp = self._make_input(power=400.0, speed=11.0, n_samples=60)  # Higher power → higher CdA
        # Long segment with typical CdA
        long_inp = self._make_input(power=315.0, speed=11.11, n_samples=240)
        
        result = estimate_cda([short_inp, long_inp])
        
        # Result should be closer to the long segment's estimate
        long_only = estimate_cda([long_inp])
        short_only = estimate_cda([short_inp])
        
        # Weighted average should be between them, closer to long
        assert abs(result.cda - long_only.cda) < abs(result.cda - short_only.cda)

    def test_invalid_estimates_filtered(self):
        """Should filter out clearly invalid CdA estimates."""
        # One reasonable input
        good_inp = self._make_input(power=315.0, speed=11.11, n_samples=120)
        # One that would give invalid CdA (very low power)
        bad_inp = self._make_input(power=50.0, speed=11.0, n_samples=120)  # Too low → CdA would be tiny
        
        result = estimate_cda([good_inp, bad_inp])
        
        # Should only use the good estimate
        assert result.n_segments == 1

    def test_all_invalid_returns_default(self):
        """All invalid estimates should return default CdA."""
        # All inputs would give invalid CdA
        bad_inputs = [
            self._make_input(power=30.0, speed=11.0, n_samples=100),
            self._make_input(power=20.0, speed=10.0, n_samples=100),
        ]
        
        result = estimate_cda(bad_inputs)
        
        assert result.cda == 0.32  # Default
        assert result.confidence == "low"
        assert result.n_segments == 0

    def test_crr_fixed_parameter(self):
        """Should use crr_fixed when provided."""
        inp = self._make_input(power=315.0, speed=11.11, n_samples=100)
        
        # Same input, different fixed Crr should give different CdA
        result_low_crr = estimate_cda([inp], crr_fixed=0.003)
        result_high_crr = estimate_cda([inp], crr_fixed=0.006)
        
        # Higher Crr means more power goes to rolling resistance,
        # leaving less for aero, so CdA estimate should be lower
        assert result_high_crr.cda < result_low_crr.cda


class TestConfidenceTier:
    """Tests for confidence_tier function."""

    def test_high_confidence(self):
        """Should return 'high' for excellent data."""
        tier = confidence_tier(
            n_segments=5,
            total_duration_s=300,
            cv=0.02,
        )
        assert tier == "high"

    def test_medium_confidence(self):
        """Should return 'medium' for good data."""
        tier = confidence_tier(
            n_segments=3,
            total_duration_s=150,
            cv=0.04,
        )
        assert tier == "medium"

    def test_low_confidence_few_segments(self):
        """Should return 'low' for too few segments."""
        tier = confidence_tier(
            n_segments=2,
            total_duration_s=300,
            cv=0.02,
        )
        assert tier == "low"

    def test_low_confidence_short_duration(self):
        """Should return 'low' for short total duration."""
        tier = confidence_tier(
            n_segments=5,
            total_duration_s=100,
            cv=0.02,
        )
        assert tier == "low"

    def test_low_confidence_high_cv(self):
        """Should return 'low' for high coefficient of variation."""
        tier = confidence_tier(
            n_segments=5,
            total_duration_s=300,
            cv=0.06,
        )
        assert tier == "low"


class TestDefaultValues:
    """Tests for default CdA and Crr values."""

    @pytest.mark.parametrize(
        "bike_type,expected_crr",
        [
            ("road", 0.004),
            ("tt", 0.003),
            ("gravel", 0.006),
            ("mtb", 0.012),
            ("ebike", 0.005),
        ],
    )
    def test_default_crr_by_type(self, bike_type, expected_crr):
        """Should return correct default Crr for each bike type."""
        assert get_default_crr(bike_type) == expected_crr

    @pytest.mark.parametrize(
        "bike_type,expected_cda",
        [
            ("road", 0.32),
            ("tt", 0.24),
            ("gravel", 0.35),
            ("mtb", 0.45),
            ("ebike", 0.35),
        ],
    )
    def test_default_cda_by_type(self, bike_type, expected_cda):
        """Should return correct default CdA for each bike type."""
        assert get_default_cda(bike_type) == expected_cda

    def test_invalid_bike_type_raises(self):
        """Unknown bike type should raise KeyError."""
        with pytest.raises(KeyError):
            get_default_crr("unicycle")
        with pytest.raises(KeyError):
            get_default_cda("unicycle")


class TestInputsFromSegments:
    """Tests for inputs_from_segments helper."""

    def test_creates_inputs_from_segments(self):
        """Should create CalibrationInputs from segments with array data."""
        segments = [
            CalibrationSegment(
                start_idx=0, end_idx=100, duration_s=100.0,
                mean_speed_mps=11.0, mean_power_w=250.0, mean_grade_pct=0.5,
                power_cv=0.05, speed_cv=0.02, quality_score=80.0,
            ),
            CalibrationSegment(
                start_idx=100, end_idx=200, duration_s=100.0,
                mean_speed_mps=10.5, mean_power_w=230.0, mean_grade_pct=0.0,
                power_cv=0.04, speed_cv=0.02, quality_score=85.0,
            ),
        ]
        
        # Create actual arrays with data
        power = np.concatenate([np.full(100, 250.0), np.full(100, 230.0)])
        speed = np.concatenate([np.full(100, 11.0), np.full(100, 10.5)])
        grade = np.concatenate([np.full(100, 0.5), np.full(100, 0.0)])
        
        inputs = inputs_from_segments(
            segments=segments,
            power=power,
            speed=speed,
            grade=grade,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        
        assert len(inputs) == 2
        # First segment
        assert len(inputs[0].power) == 100
        assert inputs[0].mean_power == 250.0
        assert inputs[0].mean_speed == 11.0
        assert inputs[0].duration_s == 100.0
        # Second segment
        assert len(inputs[1].power) == 100
        assert inputs[1].mean_power == 230.0
