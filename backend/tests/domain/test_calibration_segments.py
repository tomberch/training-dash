"""Tests for calibration segment selection (domain/calibration_segments.py).

Tests cover:
- CalibrationSegment and SegmentSelectionResult dataclasses
- Segment selection with various criteria
- Rejection reason tracking
- Drafting detection
- Quality scoring
"""

import numpy as np
import pytest

from trainingdash.domain.calibration_segments import (
    CalibrationSegment,
    SegmentSelectionResult,
    select_calibration_segments,
    detect_drafting,
    filter_drafting_segments,
    calculate_segment_quality,
)
from trainingdash.domain.physics import power_required, RiderParams


class TestCalibrationSegment:
    """Tests for CalibrationSegment dataclass."""

    def test_create_segment(self):
        """Should create a valid segment."""
        seg = CalibrationSegment(
            start_idx=0,
            end_idx=100,
            duration_s=100.0,
            mean_speed_mps=10.0,
            mean_power_w=200.0,
            mean_grade_pct=0.5,
            power_cv=0.05,
            speed_cv=0.02,
            quality_score=75.0,
        )
        assert seg.start_idx == 0
        assert seg.end_idx == 100
        assert seg.duration_s == 100.0
        assert seg.mean_speed_mps == 10.0

    def test_segment_is_frozen(self):
        """Segment should be immutable."""
        seg = CalibrationSegment(
            start_idx=0,
            end_idx=100,
            duration_s=100.0,
            mean_speed_mps=10.0,
            mean_power_w=200.0,
            mean_grade_pct=0.5,
            power_cv=0.05,
            speed_cv=0.02,
            quality_score=75.0,
        )
        with pytest.raises(AttributeError):
            seg.start_idx = 10  # type: ignore


class TestSelectCalibrationSegments:
    """Tests for select_calibration_segments function."""

    def _make_steady_segment(
        self,
        n_samples: int = 120,
        speed_mps: float = 11.0,  # ~40 km/h
        power_w: float = 250.0,
        grade_pct: float = 0.0,
        start_time: float = 0.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Create synthetic data for a steady-state segment."""
        # Add small random noise
        rng = np.random.default_rng(42)
        power = power_w + rng.normal(0, power_w * 0.02, n_samples)  # 2% noise
        speed = speed_mps + rng.normal(0, speed_mps * 0.01, n_samples)  # 1% noise
        grade = np.full(n_samples, grade_pct) + rng.normal(0, 0.1, n_samples)
        timestamps = np.arange(n_samples) + start_time
        return power, speed, grade, timestamps

    def test_empty_data_returns_empty(self):
        """Empty input should return empty result."""
        result = select_calibration_segments(
            power=np.array([]),
            speed=np.array([]),
            grade=np.array([]),
            timestamps=np.array([]),
        )
        assert result.segments == []
        assert result.total_valid_duration_s == 0.0
        assert "no_data" in result.rejection_reasons

    def test_selects_valid_segment(self):
        """Should select a segment that meets all criteria."""
        power, speed, grade, timestamps = self._make_steady_segment()
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        assert len(result.segments) == 1
        seg = result.segments[0]
        assert seg.mean_speed_mps > 8.33  # > 30 km/h
        assert abs(seg.mean_grade_pct) < 2.0
        assert seg.power_cv < 0.15
        assert seg.speed_cv < 0.05
        assert seg.duration_s >= 60

    def test_rejects_slow_speed(self):
        """Should reject segments below minimum speed."""
        power, speed, grade, timestamps = self._make_steady_segment(speed_mps=6.0)  # ~22 km/h
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        assert len(result.segments) == 0
        # No segments found because samples fail basic speed threshold

    def test_rejects_steep_grade(self):
        """Should reject segments with grade > max_grade_pct."""
        power, speed, grade, timestamps = self._make_steady_segment(grade_pct=5.0)
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        assert len(result.segments) == 0

    def test_rejects_unsteady_power(self):
        """Should reject segments with high power CV."""
        power, speed, grade, timestamps = self._make_steady_segment()
        # Add large power variations
        power[30:60] *= 1.5  # 50% higher in middle section
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        # Either no segments or they're rejected for unsteady power
        if len(result.segments) > 0:
            for seg in result.segments:
                assert seg.power_cv <= 0.15

    def test_rejects_short_segments(self):
        """Should reject segments shorter than min_duration_s."""
        power, speed, grade, timestamps = self._make_steady_segment(n_samples=30)  # 30s
        
        result = select_calibration_segments(
            power, speed, grade, timestamps, min_duration_s=60
        )
        
        assert len(result.segments) == 0
        assert "too_short" in result.rejection_reasons

    def test_tracks_rejection_reasons(self):
        """Should track why segments were rejected."""
        # Create data with mixed valid/invalid sections
        n = 300
        power = np.full(n, 200.0)
        speed = np.full(n, 11.0)  # ~40 km/h
        grade = np.zeros(n)
        timestamps = np.arange(n, dtype=float)
        
        # Make middle section slow (will be rejected)
        speed[100:150] = 5.0
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        # Should have rejection reasons tracked
        assert isinstance(result.rejection_reasons, dict)

    def test_multiple_valid_segments(self):
        """Should find multiple valid segments in ride data."""
        # Create two valid segments separated by invalid section
        p1, s1, g1, t1 = self._make_steady_segment(n_samples=120, start_time=0)
        p2, s2, g2, t2 = self._make_steady_segment(n_samples=120, start_time=200)
        
        # Invalid middle section (slow)
        n_mid = 50
        p_mid = np.full(n_mid, 100.0)
        s_mid = np.full(n_mid, 5.0)  # Slow
        g_mid = np.zeros(n_mid)
        t_mid = np.arange(n_mid) + 130
        
        power = np.concatenate([p1, p_mid, p2])
        speed = np.concatenate([s1, s_mid, s2])
        grade = np.concatenate([g1, g_mid, g2])
        timestamps = np.concatenate([t1, t_mid, t2])
        
        result = select_calibration_segments(power, speed, grade, timestamps)
        
        assert len(result.segments) == 2
        assert result.total_valid_duration_s >= 200  # At least 2x100s

    def test_custom_thresholds(self):
        """Should respect custom threshold parameters."""
        power, speed, grade, timestamps = self._make_steady_segment(speed_mps=9.0)  # ~32 km/h
        
        # With lower speed threshold, should select
        result = select_calibration_segments(
            power, speed, grade, timestamps,
            min_speed_mps=7.0,  # 25 km/h
        )
        
        assert len(result.segments) == 1


class TestSegmentQuality:
    """Tests for segment quality scoring."""

    def _make_segment(
        self,
        mean_speed_mps: float = 11.0,
        mean_grade_pct: float = 0.0,
        power_cv: float = 0.05,
        speed_cv: float = 0.02,
        duration_s: float = 120.0,
    ) -> CalibrationSegment:
        """Create a segment with specified parameters."""
        return CalibrationSegment(
            start_idx=0,
            end_idx=int(duration_s),
            duration_s=duration_s,
            mean_speed_mps=mean_speed_mps,
            mean_power_w=200.0,
            mean_grade_pct=mean_grade_pct,
            power_cv=power_cv,
            speed_cv=speed_cv,
            quality_score=0.0,  # Will be calculated
        )

    def test_higher_speed_higher_quality(self):
        """Higher speed should give higher quality score."""
        seg_slow = self._make_segment(mean_speed_mps=9.0)  # ~32 km/h
        seg_fast = self._make_segment(mean_speed_mps=13.0)  # ~47 km/h
        
        q_slow = calculate_segment_quality(seg_slow)
        q_fast = calculate_segment_quality(seg_fast)
        assert q_fast > q_slow

    def test_flatter_grade_higher_quality(self):
        """Flatter grade should give higher quality score."""
        seg_hilly = self._make_segment(mean_grade_pct=1.5)
        seg_flat = self._make_segment(mean_grade_pct=0.0)
        
        q_hilly = calculate_segment_quality(seg_hilly)
        q_flat = calculate_segment_quality(seg_flat)
        assert q_flat > q_hilly

    def test_lower_cv_higher_quality(self):
        """Lower coefficient of variation should give higher quality."""
        seg_variable = self._make_segment(power_cv=0.12, speed_cv=0.04)
        seg_steady = self._make_segment(power_cv=0.03, speed_cv=0.01)
        
        q_variable = calculate_segment_quality(seg_variable)
        q_steady = calculate_segment_quality(seg_steady)
        assert q_steady > q_variable

    def test_longer_duration_higher_quality(self):
        """Longer duration should give higher quality score."""
        seg_short = self._make_segment(duration_s=70.0)
        seg_long = self._make_segment(duration_s=180.0)
        
        q_short = calculate_segment_quality(seg_short)
        q_long = calculate_segment_quality(seg_long)
        assert q_long > q_short

    def test_quality_score_range(self):
        """Quality score should be between 0 and 100."""
        # Best case
        seg_best = self._make_segment(
            mean_speed_mps=14.0,  # ~50 km/h
            mean_grade_pct=0.0,
            power_cv=0.0,
            speed_cv=0.0,
            duration_s=300.0,
        )
        q_best = calculate_segment_quality(seg_best)
        assert 0 <= q_best <= 100

        # Worst case (within valid thresholds)
        seg_worst = self._make_segment(
            mean_speed_mps=8.5,  # Just above 30 km/h
            mean_grade_pct=1.9,  # Near 2% limit
            power_cv=0.14,
            speed_cv=0.04,
            duration_s=65.0,
        )
        q_worst = calculate_segment_quality(seg_worst)
        assert 0 <= q_worst <= 100


class TestDraftingDetection:
    """Tests for drafting detection."""

    @pytest.fixture
    def standard_rider_params(self):
        """Standard test rider parameters."""
        return {"baseline_cda": 0.32, "rider_mass": 83}

    def test_empty_data_returns_empty(self, standard_rider_params):
        """Empty input should return empty array."""
        result = detect_drafting(
            power=np.array([]),
            speed=np.array([]),
            **standard_rider_params,
        )
        assert len(result) == 0

    def test_normal_riding_not_flagged(self, standard_rider_params):
        """Normal riding should not be flagged as drafting."""
        n = 100
        speed = np.full(n, 11.0)  # ~40 km/h
        
        # Calculate expected power and use it
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        expected_power = power_required(11.0, 0.0, rider)
        power = np.full(n, expected_power)
        
        result = detect_drafting(power, speed, **standard_rider_params)
        
        # Should not flag normal riding
        assert np.sum(result) < n * 0.1  # Less than 10% flagged

    def test_low_power_flagged_as_drafting(self, standard_rider_params):
        """Abnormally low power at high speed should be flagged."""
        n = 100
        speed = np.full(n, 11.0)  # ~40 km/h
        
        # Use only 50% of expected power (drafting)
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        expected_power = power_required(11.0, 0.0, rider)
        power = np.full(n, expected_power * 0.5)
        
        result = detect_drafting(power, speed, **standard_rider_params, threshold=0.70)
        
        # Should flag most samples
        assert np.sum(result) > n * 0.8

    def test_stationary_not_flagged(self, standard_rider_params):
        """Stationary samples should not be flagged."""
        n = 100
        speed = np.full(n, 0.0)
        power = np.full(n, 0.0)
        
        result = detect_drafting(power, speed, **standard_rider_params)
        
        # Nothing flagged when not moving
        assert np.sum(result) == 0


class TestFilterDraftingSegments:
    """Tests for filtering segments with drafting."""

    @pytest.fixture
    def standard_rider_params(self):
        return {"baseline_cda": 0.32, "rider_mass": 83}

    def test_filters_drafting_segments(self, standard_rider_params):
        """Should filter out segments with significant drafting."""
        # Create two segments
        seg1 = CalibrationSegment(
            start_idx=0, end_idx=100, duration_s=100, mean_speed_mps=11.0,
            mean_power_w=200, mean_grade_pct=0, power_cv=0.05, speed_cv=0.02,
            quality_score=80.0,
        )
        seg2 = CalibrationSegment(
            start_idx=100, end_idx=200, duration_s=100, mean_speed_mps=11.0,
            mean_power_w=200, mean_grade_pct=0, power_cv=0.05, speed_cv=0.02,
            quality_score=80.0,
        )
        
        # Create data where second segment has drafting
        rider = RiderParams(mass_kg=83, cda=0.32, crr=0.004)
        expected_power = power_required(11.0, 0.0, rider)
        
        power = np.concatenate([
            np.full(100, expected_power),  # Normal
            np.full(100, expected_power * 0.5),  # Drafting
        ])
        speed = np.full(200, 11.0)
        
        filtered, rejected = filter_drafting_segments(
            segments=[seg1, seg2],
            power=power,
            speed=speed,
            **standard_rider_params,
        )
        
        # First segment should pass, second should be rejected
        assert len(filtered) == 1
        assert rejected == 1
        assert filtered[0].start_idx == 0
