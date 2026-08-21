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
        """Should create a valid calibration input."""
        inp = CalibrationInput(
            power=250.0,
            speed=11.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
            duration_s=120.0,
        )
        assert inp.power == 250.0
        assert inp.speed == 11.0
        assert inp.duration_s == 120.0

    def test_default_duration(self):
        """Should have default duration of 1.0."""
        inp = CalibrationInput(
            power=250.0,
            speed=11.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        assert inp.duration_s == 1.0


class TestSingleSegmentEstimation:
    """Tests for _estimate_cda_single_segment function."""

    def test_zero_speed_returns_zero(self):
        """Zero speed should return zero CdA."""
        inp = CalibrationInput(
            power=250.0,
            speed=0.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        assert _estimate_cda_single_segment(inp) == 0.0

    def test_reasonable_cda_estimate(self):
        """Should estimate reasonable CdA from synthetic data."""
        # Create input matching a known CdA
        # At 40 km/h (11.11 m/s) flat, with CdA=0.32, power ~315W
        inp = CalibrationInput(
            power=315.0,
            speed=11.11,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        cda = _estimate_cda_single_segment(inp)
        
        # Should be close to 0.32
        assert 0.28 < cda < 0.36

    def test_higher_power_higher_cda(self):
        """Higher power at same speed implies higher CdA."""
        inp_low = CalibrationInput(
            power=250.0,
            speed=11.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        inp_high = CalibrationInput(
            power=350.0,
            speed=11.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        
        cda_low = _estimate_cda_single_segment(inp_low)
        cda_high = _estimate_cda_single_segment(inp_high)
        
        assert cda_high > cda_low

    def test_accounts_for_grade(self):
        """Should account for grade in estimation."""
        # On a climb, same power at same speed implies lower CdA
        # (more power goes to gravity)
        inp_flat = CalibrationInput(
            power=300.0,
            speed=10.0,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        inp_climb = CalibrationInput(
            power=300.0,
            speed=10.0,
            grade=1.0,  # 1% grade
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
        )
        
        cda_flat = _estimate_cda_single_segment(inp_flat)
        cda_climb = _estimate_cda_single_segment(inp_climb)
        
        # On climb, less power available for aero → lower CdA estimate
        assert cda_climb < cda_flat


class TestEstimateCda:
    """Tests for estimate_cda function."""

    def test_empty_inputs_raises(self):
        """Empty inputs should raise ValueError."""
        with pytest.raises(ValueError, match="No calibration inputs"):
            estimate_cda([])

    def test_single_segment_estimation(self):
        """Should estimate CdA from single segment."""
        inp = CalibrationInput(
            power=315.0,
            speed=11.11,
            grade=0.0,
            air_density=1.225,
            rider_mass=83.0,
            crr=0.004,
            duration_s=120.0,
        )
        
        result = estimate_cda([inp])
        
        assert isinstance(result, CdAEstimate)
        assert 0.1 < result.cda < 0.8
        assert result.n_segments == 1
        assert result.confidence in ("low", "medium", "high")

    def test_multiple_segments_averaged(self):
        """Should average CdA across multiple segments."""
        inputs = [
            CalibrationInput(
                power=315.0, speed=11.11, grade=0.0,
                air_density=1.225, rider_mass=83.0, crr=0.004,
                duration_s=100.0,
            ),
            CalibrationInput(
                power=280.0, speed=10.5, grade=0.0,
                air_density=1.225, rider_mass=83.0, crr=0.004,
                duration_s=100.0,
            ),
            CalibrationInput(
                power=350.0, speed=11.5, grade=0.0,
                air_density=1.225, rider_mass=83.0, crr=0.004,
                duration_s=100.0,
            ),
        ]
        
        result = estimate_cda(inputs)
        
        assert result.n_segments == 3
        assert result.total_duration_s == 300.0
        assert len(result.estimates_by_segment) == 3

    def test_duration_weighted_averaging(self):
        """Longer segments should have more weight."""
        # Short segment with different CdA
        short_inp = CalibrationInput(
            power=400.0, speed=11.0, grade=0.0,  # Higher power → higher CdA estimate
            air_density=1.225, rider_mass=83.0, crr=0.004,
            duration_s=60.0,
        )
        # Long segment with typical CdA
        long_inp = CalibrationInput(
            power=315.0, speed=11.11, grade=0.0,
            air_density=1.225, rider_mass=83.0, crr=0.004,
            duration_s=240.0,
        )
        
        result = estimate_cda([short_inp, long_inp])
        
        # Result should be closer to the long segment's estimate
        long_only = estimate_cda([long_inp])
        short_only = estimate_cda([short_inp])
        
        # Weighted average should be between them, closer to long
        assert abs(result.cda - long_only.cda) < abs(result.cda - short_only.cda)

    def test_invalid_estimates_filtered(self):
        """Should filter out clearly invalid CdA estimates."""
        # One reasonable input
        good_inp = CalibrationInput(
            power=315.0, speed=11.11, grade=0.0,
            air_density=1.225, rider_mass=83.0, crr=0.004,
            duration_s=120.0,
        )
        # One that would give invalid CdA (very low power)
        bad_inp = CalibrationInput(
            power=50.0, speed=11.0, grade=0.0,  # Too low → CdA would be negative/tiny
            air_density=1.225, rider_mass=83.0, crr=0.004,
            duration_s=120.0,
        )
        
        result = estimate_cda([good_inp, bad_inp])
        
        # Should only use the good estimate
        assert result.n_segments == 1

    def test_all_invalid_returns_default(self):
        """All invalid estimates should return default CdA."""
        # All inputs would give invalid CdA
        bad_inputs = [
            CalibrationInput(
                power=30.0, speed=11.0, grade=0.0,
                air_density=1.225, rider_mass=83.0, crr=0.004,
            ),
            CalibrationInput(
                power=20.0, speed=10.0, grade=0.0,
                air_density=1.225, rider_mass=83.0, crr=0.004,
            ),
        ]
        
        result = estimate_cda(bad_inputs)
        
        assert result.cda == 0.32  # Default
        assert result.confidence == "low"
        assert result.n_segments == 0


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
        """Should create CalibrationInputs from segments."""
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
        
        # Dummy arrays (not actually used since we use segment means)
        power = np.zeros(200)
        speed = np.zeros(200)
        grade = np.zeros(200)
        
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
        assert inputs[0].power == 250.0
        assert inputs[0].speed == 11.0
        assert inputs[0].duration_s == 100.0
        assert inputs[1].power == 230.0
