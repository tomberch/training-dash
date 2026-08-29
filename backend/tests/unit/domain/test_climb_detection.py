"""Unit tests for climb detection algorithm."""

import pytest

from trainingdash.domain.climb_detection import (
    DetectedClimb,
    GradientSegment,
    categorize_climb,
    compute_gradient_segments,
    detect_climbs,
    smooth_elevation_simple,
)


class TestCategorizeClimb:
    """Tests for climb categorization using length × grade formula."""

    def test_hc_climb(self):
        """HC climb: score >= 80,000 (10km at 8%)."""
        assert categorize_climb(10000, 8.0) == "hc"
        assert categorize_climb(20000, 5.0) == "hc"  # 100,000
        assert categorize_climb(8000, 10.0) == "hc"  # 80,000 exactly

    def test_cat1_climb(self):
        """Cat 1 climb: score >= 64,000 but < 80,000."""
        assert categorize_climb(8000, 8.0) == "1"  # 64,000 exactly
        assert categorize_climb(10000, 7.0) == "1"  # 70,000
        assert categorize_climb(6400, 10.0) == "1"  # 64,000

    def test_cat2_climb(self):
        """Cat 2 climb: score >= 32,000 but < 64,000."""
        assert categorize_climb(4000, 8.0) == "2"  # 32,000 exactly
        assert categorize_climb(5000, 7.0) == "2"  # 35,000
        assert categorize_climb(8000, 5.0) == "2"  # 40,000

    def test_cat3_climb(self):
        """Cat 3 climb: score >= 16,000 but < 32,000."""
        assert categorize_climb(2000, 8.0) == "3"  # 16,000 exactly
        assert categorize_climb(3000, 6.0) == "3"  # 18,000
        assert categorize_climb(4000, 5.0) == "3"  # 20,000

    def test_cat4_climb(self):
        """Cat 4 climb: score >= 8,000 but < 16,000."""
        assert categorize_climb(1000, 8.0) == "4"  # 8,000 exactly
        assert categorize_climb(2000, 5.0) == "4"  # 10,000
        assert categorize_climb(1500, 6.0) == "4"  # 9,000

    def test_nc_climb(self):
        """NC (uncategorized) climb: score < 8,000."""
        assert categorize_climb(1000, 5.0) == "nc"  # 5,000
        assert categorize_climb(500, 10.0) == "nc"  # 5,000
        assert categorize_climb(2000, 3.0) == "nc"  # 6,000

    def test_boundary_values(self):
        """Test exact boundary values."""
        # Just below HC threshold
        assert categorize_climb(7999, 10.0) == "1"  # 79,990
        # Just at HC threshold
        assert categorize_climb(8000, 10.0) == "hc"  # 80,000


class TestSmoothElevationSimple:
    """Tests for simple moving average elevation smoothing."""

    def test_smooth_constant_elevation(self):
        """Constant elevation should remain constant."""
        altitudes = [100.0, 100.0, 100.0, 100.0, 100.0]
        result = smooth_elevation_simple(altitudes)
        assert all(v == 100.0 for v in result)

    def test_smooth_linear_increase(self):
        """Linear increase should be preserved (smoothed)."""
        altitudes = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0]
        result = smooth_elevation_simple(altitudes, window=3)
        # Middle values should be averaged
        assert abs(result[3] - 130.0) < 0.1

    def test_smooth_removes_noise(self):
        """Smoothing should reduce noise."""
        # Linear trend with noise
        altitudes = [100.0, 115.0, 118.0, 128.0, 142.0]
        result = smooth_elevation_simple(altitudes, window=3)
        # Result should be smoother than input
        assert len(result) == len(altitudes)

    def test_smooth_short_array(self):
        """Short array (less than window) should return copy."""
        altitudes = [100.0, 110.0]
        result = smooth_elevation_simple(altitudes, window=5)
        assert result == altitudes

    def test_smooth_empty_array(self):
        """Empty array should return empty."""
        result = smooth_elevation_simple([])
        assert result == []


class TestComputeGradientSegments:
    """Tests for gradient segment computation."""

    def test_steady_climb(self):
        """Steady 5% climb should produce consistent gradient segments."""
        records = [
            {"distance_m": 0, "altitude_m": 100.0},
            {"distance_m": 50, "altitude_m": 102.5},
            {"distance_m": 100, "altitude_m": 105.0},
            {"distance_m": 150, "altitude_m": 107.5},
            {"distance_m": 200, "altitude_m": 110.0},
        ]
        segments = compute_gradient_segments(records, segment_length_m=50.0)

        assert len(segments) >= 1
        # All segments should be ~5%
        for seg in segments:
            assert abs(seg.grade_pct - 5.0) < 1.0  # Allow some smoothing variation

    def test_flat_terrain(self):
        """Flat terrain should have ~0% gradient."""
        records = [
            {"distance_m": 0, "altitude_m": 100.0},
            {"distance_m": 100, "altitude_m": 100.0},
            {"distance_m": 200, "altitude_m": 100.0},
        ]
        segments = compute_gradient_segments(records, segment_length_m=50.0)

        for seg in segments:
            assert abs(seg.grade_pct) < 0.5

    def test_descent(self):
        """Descent should produce negative gradient."""
        records = [
            {"distance_m": 0, "altitude_m": 200.0},
            {"distance_m": 100, "altitude_m": 190.0},
            {"distance_m": 200, "altitude_m": 180.0},
        ]
        segments = compute_gradient_segments(records, segment_length_m=50.0)

        # Should have negative grades
        assert any(seg.grade_pct < -5.0 for seg in segments)

    def test_single_segment_short_distance(self):
        """Very short distance should produce single segment."""
        records = [
            {"distance_m": 0, "altitude_m": 100.0},
            {"distance_m": 30, "altitude_m": 103.0},
        ]
        segments = compute_gradient_segments(records, segment_length_m=50.0)

        assert len(segments) == 1
        assert abs(segments[0].grade_pct - 10.0) < 1.0

    def test_empty_records(self):
        """Empty records should return empty segments."""
        assert compute_gradient_segments([]) == []
        assert compute_gradient_segments([{"distance_m": 0, "altitude_m": 100}]) == []


class TestDetectClimbs:
    """Tests for the main climb detection algorithm."""

    def test_simple_steady_climb(self):
        """Detect a simple steady 5% climb over 1km."""
        records = []
        for i in range(21):  # 0 to 1000m in 50m steps
            distance = i * 50
            altitude = 100 + (distance * 0.05)  # 5% grade
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        climb = climbs[0]
        assert abs(climb.distance_m - 1000) < 100
        assert abs(climb.avg_grade_pct - 5.0) < 1.0
        assert climb.category == "nc"  # 1000m × 5% = 5000, below Cat 4

    def test_cat4_climb(self):
        """Detect a Cat 4 climb (1.5km at 8% to ensure score > 8000 after smoothing)."""
        records = []
        for i in range(31):  # 1500m
            distance = i * 50
            altitude = 100 + (distance * 0.08)  # 8% grade
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        # Score should be ~1500 × 8 = 12000, which is Cat 4
        assert climbs[0].category == "4"

    def test_cat2_climb(self):
        """Detect a Cat 2 climb (5km at 8% to ensure score > 32000 after smoothing)."""
        records = []
        for i in range(101):  # 5000m
            distance = i * 50
            altitude = 100 + (distance * 0.08)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        # Score should be ~5000 × 8 = 40000, which is Cat 2
        assert climbs[0].category == "2"

    def test_hc_climb_alpe_dhuez_style(self):
        """Detect an HC climb similar to Alpe d'Huez (13km at 8%)."""
        records = []
        for i in range(261):
            distance = i * 50
            altitude = 720 + (distance * 0.08)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        assert climbs[0].category == "hc"  # 13000m × 8% = 104000

    def test_climb_with_flat_section_merged(self):
        """Flat section mid-climb should be merged if short enough."""
        records = []
        # First part: 500m climb at 6%
        for i in range(11):
            distance = i * 50
            altitude = 100 + (distance * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        # Flat section: 300m at 0%
        last_alt = records[-1]["altitude_m"]
        for i in range(1, 7):
            distance = 500 + (i * 50)
            records.append({"distance_m": distance, "altitude_m": last_alt})

        # Second part: 500m climb at 6%
        base_dist = 800
        base_alt = last_alt
        for i in range(1, 11):
            distance = base_dist + (i * 50)
            altitude = base_alt + ((distance - base_dist) * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(
            records,
            min_grade_pct=3.0,
            min_length_m=300,
            merge_gap_m=500,
            merge_max_drop_m=20,
        )

        # Should merge into one climb since gap is < 500m
        assert len(climbs) == 1
        assert climbs[0].distance_m > 1000

    def test_climb_with_descent_split(self):
        """Descent mid-climb should split into two climbs if drop > threshold."""
        records = []
        # First climb: 600m at 6%
        for i in range(13):
            distance = i * 50
            altitude = 100 + (distance * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        # Significant descent: 400m dropping 50m (well above 20m threshold)
        last_alt = records[-1]["altitude_m"]
        for i in range(1, 9):
            distance = 600 + (i * 50)
            altitude = last_alt - (i * 6.25)  # Drop 50m over 400m
            records.append({"distance_m": distance, "altitude_m": altitude})

        # Second climb: 600m at 6%
        base_dist = 1000
        base_alt = records[-1]["altitude_m"]
        for i in range(1, 13):
            distance = base_dist + (i * 50)
            altitude = base_alt + ((distance - base_dist) * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(
            records,
            min_grade_pct=3.0,
            min_length_m=300,
            merge_gap_m=500,
            merge_max_drop_m=20,  # 50m drop > 20m threshold
        )

        # Should be two separate climbs due to significant descent
        assert len(climbs) == 2

    def test_short_steep_section_filtered(self):
        """Very short steep section should be filtered out."""
        records = [
            {"distance_m": 0, "altitude_m": 100},
            {"distance_m": 50, "altitude_m": 105},
            {"distance_m": 100, "altitude_m": 110},
            {"distance_m": 150, "altitude_m": 115},  # 100m at 10%
            {"distance_m": 200, "altitude_m": 115},
            {"distance_m": 300, "altitude_m": 115},
        ]

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        # Should be filtered out (< 300m)
        assert len(climbs) == 0

    def test_flat_ride_no_climbs(self):
        """Completely flat ride should detect no climbs."""
        records = []
        for i in range(21):
            records.append({"distance_m": i * 100, "altitude_m": 100})

        climbs = detect_climbs(records)
        assert len(climbs) == 0

    def test_gradual_climb_below_threshold(self):
        """2% grade climb should not be detected (below 3% threshold)."""
        records = []
        for i in range(51):
            distance = i * 100
            altitude = 100 + (distance * 0.02)  # 2% grade
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0)
        assert len(climbs) == 0

    def test_noisy_gps_data(self):
        """Algorithm should handle noisy GPS elevation data."""
        import random

        random.seed(42)

        records = []
        for i in range(41):
            distance = i * 50
            # Base 5% climb with ±3m noise
            altitude = 100 + (distance * 0.05) + random.uniform(-3, 3)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        # Should still detect the underlying climb
        assert len(climbs) >= 1
        # Average grade should be approximately 5% despite noise
        assert abs(climbs[0].avg_grade_pct - 5.0) < 2.0

    def test_multiple_distinct_climbs(self):
        """Detect multiple climbs separated by flat/descent."""
        records = []

        # Climb 1: 500m at 6%
        for i in range(11):
            distance = i * 50
            altitude = 100 + (distance * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        # Long flat: 1km
        last_alt = records[-1]["altitude_m"]
        for i in range(1, 21):
            distance = 500 + (i * 50)
            records.append({"distance_m": distance, "altitude_m": last_alt})

        # Climb 2: 600m at 8%
        base_dist = 1500
        for i in range(1, 13):
            distance = base_dist + (i * 50)
            altitude = last_alt + ((distance - base_dist) * 0.08)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(
            records,
            min_grade_pct=3.0,
            min_length_m=300,
            merge_gap_m=500,  # 1km gap > 500m threshold
        )

        assert len(climbs) == 2
        # Second climb should be steeper
        assert climbs[1].avg_grade_pct > climbs[0].avg_grade_pct

    def test_climb_metrics_accuracy(self):
        """Verify climb metrics are calculated accurately."""
        records = []
        for i in range(21):
            distance = i * 50
            altitude = 100 + (distance * 0.05)  # Exactly 5%
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        climb = climbs[0]

        # Check elevation gain (1000m × 5% = 50m)
        assert abs(climb.elevation_gain_m - 50) < 5

        # Check gradient segments exist
        assert len(climb.gradient_segments) > 0

    def test_empty_records(self):
        """Empty records should return empty list."""
        assert detect_climbs([]) == []

    def test_single_record(self):
        """Single record should return empty list."""
        assert detect_climbs([{"distance_m": 0, "altitude_m": 100}]) == []

    def test_descent_only(self):
        """Descent-only ride should detect no climbs."""
        records = []
        for i in range(21):
            distance = i * 50
            altitude = 200 - (distance * 0.05)  # -5% grade
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records)
        assert len(climbs) == 0

    def test_gradient_segments_in_climb(self):
        """Verify gradient segments are generated for detected climbs."""
        records = []
        for i in range(41):
            distance = i * 25
            altitude = 100 + (distance * 0.06)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300, segment_length_m=50)

        assert len(climbs) == 1
        # Should have multiple gradient segments
        assert len(climbs[0].gradient_segments) >= 10

    def test_variable_grade_climb(self):
        """Climb with varying gradient should be detected and averaged."""
        records = []
        # 500m at 4%, then 500m at 8%
        for i in range(11):
            distance = i * 50
            altitude = 100 + (distance * 0.04)
            records.append({"distance_m": distance, "altitude_m": altitude})

        base_alt = records[-1]["altitude_m"]
        for i in range(1, 11):
            distance = 500 + (i * 50)
            altitude = base_alt + ((distance - 500) * 0.08)
            records.append({"distance_m": distance, "altitude_m": altitude})

        climbs = detect_climbs(records, min_grade_pct=3.0, min_length_m=300)

        assert len(climbs) == 1
        # Average should be ~6%
        assert 4.0 < climbs[0].avg_grade_pct < 8.0
        # Max grade should be ~8%
        assert climbs[0].max_grade_pct > 6.0


class TestGradientSegmentDataclass:
    """Tests for GradientSegment dataclass."""

    def test_creation(self):
        """Can create GradientSegment with required fields."""
        seg = GradientSegment(distance_m=50.0, grade_pct=5.5)
        assert seg.distance_m == 50.0
        assert seg.grade_pct == 5.5


class TestDetectedClimbDataclass:
    """Tests for DetectedClimb dataclass."""

    def test_creation(self):
        """Can create DetectedClimb with all fields."""
        climb = DetectedClimb(
            start_index=10,
            end_index=50,
            distance_m=2000.0,
            elevation_gain_m=160.0,
            avg_grade_pct=8.0,
            max_grade_pct=12.0,
            category="3",
            gradient_segments=[
                GradientSegment(distance_m=50, grade_pct=7.0),
                GradientSegment(distance_m=50, grade_pct=9.0),
            ],
        )
        assert climb.start_index == 10
        assert climb.end_index == 50
        assert climb.distance_m == 2000.0
        assert climb.category == "3"
        assert len(climb.gradient_segments) == 2
