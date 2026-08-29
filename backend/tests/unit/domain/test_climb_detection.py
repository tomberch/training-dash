"""Tests for climb detection algorithm."""

import pytest

from trainingdash.domain.climb_detection import (
    DetectedClimb,
    categorize_climb,
    detect_climbs,
    smooth_elevation,
)


def make_records(
    altitudes: list[float],
    distances: list[float] | None = None,
    interval_m: float = 50.0,
) -> list[dict]:
    """
    Create test records from altitude profile.

    Args:
        altitudes: List of altitude values
        distances: Optional list of cumulative distances (auto-generated if None)
        interval_m: Distance interval between points if distances not provided
    """
    if distances is None:
        distances = [i * interval_m for i in range(len(altitudes))]

    return [{"altitude_m": alt, "distance_m": dist} for alt, dist in zip(altitudes, distances)]


# =============================================================================
# Smooth Elevation Tests
# =============================================================================


class TestSmoothElevation:
    """Tests for smooth_elevation function."""

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = smooth_elevation([])
        assert result == []

    def test_single_value(self):
        """Single value returns same value."""
        result = smooth_elevation([100.0])
        assert result == [100.0]

    def test_two_values(self):
        """Two values are averaged appropriately."""
        result = smooth_elevation([100.0, 110.0])
        assert len(result) == 2
        # First point: average of [100, 110] = 105
        # Second point: average of [100, 110] = 105
        assert result[0] == pytest.approx(105.0)
        assert result[1] == pytest.approx(105.0)

    def test_constant_elevation(self):
        """Constant elevation stays constant."""
        altitudes = [500.0] * 10
        result = smooth_elevation(altitudes)
        assert all(a == pytest.approx(500.0) for a in result)

    def test_linear_increase_preserved(self):
        """Linear increase is preserved (centered average)."""
        altitudes = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        result = smooth_elevation(altitudes, window=3)
        # Middle values should be close to original
        assert result[4] == pytest.approx(40.0, abs=0.1)

    def test_spike_smoothed(self):
        """GPS spike is smoothed out."""
        altitudes = [100.0, 100.0, 150.0, 100.0, 100.0]  # Spike at index 2
        result = smooth_elevation(altitudes, window=5)
        # Spike should be reduced
        assert result[2] < 130.0  # Much less than 150

    def test_output_length_matches_input(self):
        """Output length always matches input."""
        for length in [1, 2, 5, 10, 100]:
            altitudes = list(range(length))
            result = smooth_elevation(altitudes)
            assert len(result) == length

    def test_window_size_3(self):
        """Test with window size 3."""
        altitudes = [0.0, 10.0, 20.0, 30.0, 40.0]
        result = smooth_elevation(altitudes, window=3)
        # Index 2: average of [10, 20, 30] = 20
        assert result[2] == pytest.approx(20.0)


# =============================================================================
# Categorize Climb Tests
# =============================================================================


class TestCategorizeClimb:
    """Tests for categorize_climb function."""

    def test_hc_climb(self):
        """HC: score >= 80,000."""
        # Alpe d'Huez style: 13.8km at 8.1% = 111,780
        assert categorize_climb(13800, 8.1) == "hc"
        # Threshold: 10km at 8% = 80,000
        assert categorize_climb(10000, 8.0) == "hc"

    def test_cat1_climb(self):
        """Cat 1: score >= 64,000."""
        # 8km at 8% = 64,000
        assert categorize_climb(8000, 8.0) == "1"
        # Just under HC
        assert categorize_climb(9000, 8.0) == "1"  # 72,000

    def test_cat2_climb(self):
        """Cat 2: score >= 32,000."""
        # 4km at 8% = 32,000
        assert categorize_climb(4000, 8.0) == "2"
        # 8km at 5% = 40,000
        assert categorize_climb(8000, 5.0) == "2"

    def test_cat3_climb(self):
        """Cat 3: score >= 16,000."""
        # 2km at 8% = 16,000
        assert categorize_climb(2000, 8.0) == "3"
        # 4km at 5% = 20,000
        assert categorize_climb(4000, 5.0) == "3"

    def test_cat4_climb(self):
        """Cat 4: score >= 8,000."""
        # 1km at 8% = 8,000
        assert categorize_climb(1000, 8.0) == "4"
        # 2km at 5% = 10,000
        assert categorize_climb(2000, 5.0) == "4"

    def test_nc_climb(self):
        """NC (not categorized): score < 8,000."""
        # 500m at 6% = 3,000
        assert categorize_climb(500, 6.0) == "nc"
        # 1km at 3% = 3,000
        assert categorize_climb(1000, 3.0) == "nc"

    def test_boundary_values(self):
        """Test exact boundary values."""
        # Just at HC boundary
        assert categorize_climb(10000, 8.0) == "hc"  # 80,000
        # Just below HC
        assert categorize_climb(9999, 8.0) == "1"  # 79,992

    def test_zero_values(self):
        """Zero distance or grade returns NC."""
        assert categorize_climb(0, 8.0) == "nc"
        assert categorize_climb(1000, 0) == "nc"

    def test_negative_grade(self):
        """Negative grade (descent) returns NC."""
        assert categorize_climb(1000, -5.0) == "nc"


# =============================================================================
# Detect Climbs Tests
# =============================================================================


class TestDetectClimbs:
    """Tests for detect_climbs main function."""

    def test_empty_records(self):
        """Empty records returns empty list."""
        result = detect_climbs([])
        assert result == []

    def test_single_record(self):
        """Single record returns empty list."""
        result = detect_climbs([{"altitude_m": 100, "distance_m": 0}])
        assert result == []

    def test_flat_ride(self):
        """Flat ride with no climbing returns empty list."""
        records = make_records([100.0] * 100)
        result = detect_climbs(records)
        assert result == []

    def test_simple_steady_climb(self):
        """Simple steady 5% climb should be detected."""
        # 2km at 5% = 100m elevation gain
        altitudes = [500 + i * 5 for i in range(41)]  # 0 to 2000m, 5m gain per 100m
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 1
        climb = result[0]
        assert climb.distance_m >= 1500  # Most of the climb
        assert climb.avg_grade_pct > 4.0  # Close to 5%
        assert climb.category in ["4", "3"]  # 2000 * 5 = 10,000 = Cat 4

    def test_climb_with_flat_section_merged(self):
        """Climb with short flat section in middle should be merged."""
        # 500m climb, 200m flat, 500m climb
        altitudes = []
        distance = 0
        distances = []

        # First climb: 500m at 8%
        for i in range(11):
            altitudes.append(500 + i * 4)  # 40m gain
            distances.append(distance)
            distance += 50

        # Flat section: 200m
        for i in range(4):
            altitudes.append(altitudes[-1])
            distances.append(distance)
            distance += 50

        # Second climb: 500m at 8%
        for i in range(11):
            altitudes.append(altitudes[-1] + 4)
            distances.append(distance)
            distance += 50

        records = make_records(altitudes, distances)
        result = detect_climbs(records, min_grade_pct=3.0, merge_gap_m=500)

        # Should merge into single climb
        assert len(result) == 1
        assert result[0].distance_m > 1000

    def test_climb_with_descent_splits(self):
        """Climb with significant descent in middle should split."""
        # 500m climb, 300m descent (50m drop), 500m climb
        altitudes = []
        distance = 0
        distances = []

        # First climb: 500m at 8%
        for i in range(11):
            altitudes.append(500 + i * 4)
            distances.append(distance)
            distance += 50

        # Descent: 300m with 50m drop (more pronounced to survive smoothing)
        for i in range(7):
            altitudes.append(altitudes[-1] - 8)
            distances.append(distance)
            distance += 50

        # Second climb: 500m at 8%
        for i in range(11):
            altitudes.append(altitudes[-1] + 4)
            distances.append(distance)
            distance += 50

        records = make_records(altitudes, distances)
        result = detect_climbs(records, min_grade_pct=3.0, merge_max_drop_m=20, min_length_m=300)

        # Should split into two climbs (drop > 20m even after smoothing)
        assert len(result) == 2

    def test_short_climb_filtered(self):
        """Climb shorter than min_length_m should be filtered."""
        # 200m climb at 8%
        altitudes = [500 + i * 4 for i in range(5)]  # 0 to 200m
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_length_m=300)

        assert len(result) == 0  # Too short

    def test_gradual_climb_below_threshold(self):
        """Climb below min_grade_pct should not be detected."""
        # 2km at 2% (below 3% threshold)
        altitudes = [500 + i * 1 for i in range(41)]  # 1m per 50m = 2%
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0)

        assert len(result) == 0

    def test_hc_climb_detected(self):
        """Long steep climb should be categorized as HC."""
        # 12km at 8% = 96,000 = HC
        # 240 points at 50m intervals = 12km
        altitudes = [500 + i * 4 for i in range(241)]  # 4m per 50m = 8%
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 1
        assert result[0].category == "hc"

    def test_cat4_climb_detected(self):
        """Short moderate climb should be Cat 4."""
        # 1.5km at 6% = 9,000 = Cat 4
        altitudes = [500 + i * 3 for i in range(31)]  # 3m per 50m = 6%
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 1
        assert result[0].category == "4"

    def test_multiple_climbs(self):
        """Multiple separate climbs should all be detected."""
        altitudes = []
        distances = []
        distance = 0

        # Climb 1: 1km at 6%
        for i in range(21):
            altitudes.append(500 + i * 3)
            distances.append(distance)
            distance += 50

        # Flat/descent: 2km
        base_alt = altitudes[-1]
        for i in range(40):
            altitudes.append(base_alt - 5)  # Slight descent
            distances.append(distance)
            distance += 50

        # Climb 2: 1.5km at 8%
        base_alt = altitudes[-1]
        for i in range(31):
            altitudes.append(base_alt + i * 4)
            distances.append(distance)
            distance += 50

        records = make_records(altitudes, distances)
        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 2

    def test_climb_indices_correct(self):
        """Start and end indices should be correct."""
        # Flat, then climb, then flat
        altitudes = [100.0] * 20 + [100 + i * 5 for i in range(21)] + [200.0] * 20
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 1
        climb = result[0]
        # Climb starts around index 20 and ends around index 40
        assert climb.start_index >= 15
        assert climb.start_index <= 25
        assert climb.end_index >= 35
        assert climb.end_index <= 45

    def test_gradient_segments_generated(self):
        """Climb should have gradient segments."""
        altitudes = [500 + i * 4 for i in range(41)]  # 2km at 8%
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, segment_length_m=100)

        assert len(result) == 1
        assert len(result[0].gradient_segments) > 0
        # Each segment should be ~100m
        for seg in result[0].gradient_segments:
            assert 50 <= seg.distance_m <= 150

    def test_max_grade_tracked(self):
        """Max grade should reflect steepest section."""
        # Variable grade climb: starts easy, gets steep
        altitudes = []
        alt = 500
        for i in range(11):
            altitudes.append(alt)
            alt += 2  # 4%
        for i in range(11):
            altitudes.append(alt)
            alt += 6  # 12%

        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(result) == 1
        # Max grade should be around 12%
        assert result[0].max_grade_pct > 10.0

    def test_noisy_gps_smoothed(self):
        """Noisy GPS data should be smoothed before detection."""
        # Base 6% climb with noise
        base_altitudes = [500 + i * 3 for i in range(41)]
        # Add noise: ±5m random-ish spikes
        noise = [0, 5, -5, 3, -3, 4, -4, 2, -2, 1] * 5
        altitudes = [b + n for b, n in zip(base_altitudes, noise[:41])]

        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        # Should still detect the climb despite noise
        assert len(result) >= 1
        # Average grade should be close to 6% (smoothing removes noise)
        assert 4.0 < result[0].avg_grade_pct < 8.0

    def test_descent_not_detected(self):
        """Pure descent should not be detected as a climb."""
        altitudes = [600 - i * 5 for i in range(41)]  # Descending
        records = make_records(altitudes, interval_m=50)

        result = detect_climbs(records, min_grade_pct=3.0)

        assert len(result) == 0


class TestDetectedClimbDataclass:
    """Tests for DetectedClimb dataclass."""

    def test_dataclass_fields(self):
        """Verify all expected fields exist."""
        from trainingdash.domain.segment_geometry import GradientSegment

        climb = DetectedClimb(
            start_index=100,
            end_index=200,
            distance_m=2000.0,
            elevation_gain_m=160.0,
            avg_grade_pct=8.0,
            max_grade_pct=12.0,
            category="3",
            gradient_segments=[GradientSegment(500.0, 8.0)],
        )

        assert climb.start_index == 100
        assert climb.end_index == 200
        assert climb.distance_m == 2000.0
        assert climb.category == "3"
        assert len(climb.gradient_segments) == 1


class TestEdgeCases:
    """Edge case tests for climb detection."""

    def test_all_same_altitude(self):
        """All points at same altitude returns no climbs."""
        records = make_records([500.0] * 100)
        result = detect_climbs(records)
        assert result == []

    def test_very_short_record_list(self):
        """Very short record list handled gracefully."""
        records = make_records([500, 510])
        result = detect_climbs(records, min_length_m=10)
        # May or may not detect depending on thresholds, but shouldn't crash
        assert isinstance(result, list)

    def test_missing_altitude_uses_default(self):
        """Records missing altitude_m use default of 0."""
        records = [{"distance_m": i * 50} for i in range(20)]
        result = detect_climbs(records)
        assert result == []  # All at 0 altitude = flat

    def test_missing_distance_uses_default(self):
        """Records missing distance_m use default of 0."""
        records = [{"altitude_m": 500 + i * 5} for i in range(20)]
        result = detect_climbs(records)
        # All at distance 0 = no movement, no climbs
        assert result == []

    def test_custom_parameters(self):
        """Custom detection parameters are respected."""
        # Climb at 2.5% (below default 3% threshold)
        altitudes = [500 + i * 1.25 for i in range(81)]  # 4km at 2.5%
        records = make_records(altitudes, interval_m=50)

        # Should not detect with default threshold
        result_default = detect_climbs(records, min_grade_pct=3.0)
        assert len(result_default) == 0

        # Should detect with lower threshold
        result_custom = detect_climbs(records, min_grade_pct=2.0, min_length_m=300)
        assert len(result_custom) == 1
