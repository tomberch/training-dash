"""Unit tests for course segmentation module."""

import numpy as np
import pytest

from trainingdash.domain.course_segmentation import (
    Climb,
    CourseSegment,
    _categorize_climb,
    assign_segment_bearings,
    detect_climbs,
    segment_course,
)


class TestSegmentCourse:
    """Tests for course segmentation."""

    def test_constant_grade_single_segment(self):
        """Constant grade should produce a single segment."""
        distances = np.array([0, 100, 200, 300, 400, 500])
        grades = np.array([0.05, 0.05, 0.05, 0.05, 0.05, 0.05])  # 5% throughout
        elevations = np.array([100, 105, 110, 115, 120, 125])

        segments = segment_course(distances, grades, elevations)

        assert len(segments) == 1
        assert segments[0].start_distance_m == 0
        assert segments[0].end_distance_m == 500
        assert segments[0].avg_grade_pct == pytest.approx(5.0, rel=0.1)
        assert segments[0].terrain_type == "climb"

    def test_grade_change_creates_segments(self):
        """Significant grade change should create new segment."""
        # 5% climb for 500m, then flat for 500m
        distances = np.array([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000])
        grades = np.array([0.05, 0.05, 0.05, 0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        elevations = np.array([100, 105, 110, 115, 120, 125, 125, 125, 125, 125, 125])

        segments = segment_course(distances, grades, elevations, min_segment_m=200)

        assert len(segments) >= 2
        # First segment should be climbing
        assert segments[0].avg_grade_pct > 2.0
        # Last segment should be flat
        assert abs(segments[-1].avg_grade_pct) < 2.0

    def test_minimum_segment_length_respected(self):
        """Segments shorter than minimum should be merged."""
        # Short grade changes that should be merged
        distances = np.array([0, 50, 100, 150, 200, 500, 600])
        grades = np.array([0.05, 0.0, 0.05, 0.0, 0.05, 0.05, 0.05])
        elevations = np.array([100, 102.5, 105, 105, 107.5, 125, 130])

        segments = segment_course(distances, grades, elevations, min_segment_m=200)

        # Short oscillations should be merged
        for seg in segments:
            assert seg.length_m >= 200 or seg == segments[-1]

    def test_flat_course(self):
        """Completely flat course should produce single flat segment."""
        distances = np.array([0, 100, 200, 300, 400])
        grades = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
        elevations = np.array([100, 100, 100, 100, 100])

        segments = segment_course(distances, grades, elevations)

        assert len(segments) == 1
        assert segments[0].terrain_type == "flat"
        assert segments[0].avg_grade_pct == pytest.approx(0.0)

    def test_all_climb_course(self):
        """Steep climb throughout should produce single climbing segment."""
        distances = np.array([0, 100, 200, 300, 400])
        grades = np.array([0.10, 0.10, 0.10, 0.10, 0.10])  # 10%
        elevations = np.array([100, 110, 120, 130, 140])

        segments = segment_course(distances, grades, elevations)

        assert len(segments) == 1
        assert segments[0].terrain_type == "steep_climb"

    def test_short_course(self):
        """Very short course should still produce valid segments."""
        distances = np.array([0, 100])
        grades = np.array([0.05, 0.05])
        elevations = np.array([100, 105])

        segments = segment_course(distances, grades, elevations, min_segment_m=50)

        assert len(segments) == 1
        assert segments[0].length_m == 100

    def test_empty_course(self):
        """Empty input should return empty list."""
        segments = segment_course([], [], [])
        assert segments == []

    def test_single_point(self):
        """Single point should return empty list."""
        segments = segment_course([0], [0.05], [100])
        assert segments == []

    def test_elevation_gain_loss_tracking(self):
        """Segments should track elevation gain and loss correctly."""
        # Climb then descent
        distances = np.array([0, 500, 1000])
        grades = np.array([0.08, 0.08, -0.06])
        elevations = np.array([100, 140, 110])

        segments = segment_course(distances, grades, elevations, grade_threshold_pct=5.0, min_segment_m=200)

        # Find climbing and descending segments
        climbing = [s for s in segments if s.avg_grade_pct > 0]
        descending = [s for s in segments if s.avg_grade_pct < 0]

        if climbing:
            assert climbing[0].elevation_gain_m > 0
            assert climbing[0].elevation_loss_m == 0
        if descending:
            assert descending[0].elevation_loss_m > 0

    def test_accepts_lists(self):
        """Should accept Python lists."""
        distances = [0, 100, 200, 300]
        grades = [0.05, 0.05, 0.05, 0.05]
        elevations = [100, 105, 110, 115]

        segments = segment_course(distances, grades, elevations)

        assert len(segments) >= 1


class TestDetectClimbs:
    """Tests for climb detection."""

    def test_detect_single_climb(self):
        """Should detect a single climb."""
        segments = [
            CourseSegment(0, 500, 500, 1.0, 5, 0, "flat"),
            CourseSegment(500, 2000, 1500, 6.0, 90, 0, "climb"),
            CourseSegment(2000, 3000, 1000, 0.0, 0, 0, "flat"),
        ]

        climbs = detect_climbs(segments)

        assert len(climbs) == 1
        assert climbs[0].start_distance_m == 500
        assert climbs[0].end_distance_m == 2000
        assert climbs[0].length_m == 1500
        assert climbs[0].avg_grade_pct == pytest.approx(6.0)

    def test_merge_adjacent_climbing_segments(self):
        """Adjacent climbing segments should merge into one climb."""
        segments = [
            CourseSegment(0, 500, 500, 0.0, 0, 0, "flat"),
            CourseSegment(500, 1000, 500, 5.0, 25, 0, "climb"),
            CourseSegment(1000, 1500, 500, 7.0, 35, 0, "climb"),
            CourseSegment(1500, 2000, 500, 4.0, 20, 0, "climb"),
            CourseSegment(2000, 2500, 500, 0.0, 0, 0, "flat"),
        ]

        climbs = detect_climbs(segments)

        assert len(climbs) == 1
        assert climbs[0].start_distance_m == 500
        assert climbs[0].end_distance_m == 2000
        assert climbs[0].length_m == 1500

    def test_multiple_climbs(self):
        """Should detect multiple separate climbs."""
        segments = [
            CourseSegment(0, 1000, 1000, 5.0, 50, 0, "climb"),
            CourseSegment(1000, 2000, 1000, 0.0, 0, 0, "flat"),
            CourseSegment(2000, 3000, 1000, 6.0, 60, 0, "climb"),
        ]

        climbs = detect_climbs(segments)

        assert len(climbs) == 2
        assert climbs[0].start_distance_m == 0
        assert climbs[1].start_distance_m == 2000

    def test_minimum_length_filter(self):
        """Climbs shorter than minimum should be excluded."""
        segments = [
            CourseSegment(0, 100, 100, 8.0, 8, 0, "steep_climb"),  # Too short
            CourseSegment(100, 500, 400, 0.0, 0, 0, "flat"),
            CourseSegment(500, 1500, 1000, 5.0, 50, 0, "climb"),  # Long enough
        ]

        climbs = detect_climbs(segments, min_length_m=300)

        assert len(climbs) == 1
        assert climbs[0].start_distance_m == 500

    def test_minimum_grade_filter(self):
        """Segments below minimum grade should not be considered climbing."""
        segments = [
            CourseSegment(0, 1000, 1000, 2.0, 20, 0, "false_flat"),  # Below threshold
            CourseSegment(1000, 2000, 1000, 5.0, 50, 0, "climb"),  # Above threshold
        ]

        climbs = detect_climbs(segments, min_grade_pct=3.0)

        assert len(climbs) == 1
        assert climbs[0].start_distance_m == 1000

    def test_no_climbs_on_flat_course(self):
        """Flat course should have no climbs."""
        segments = [
            CourseSegment(0, 1000, 1000, 0.0, 0, 0, "flat"),
            CourseSegment(1000, 2000, 1000, 1.0, 10, 0, "flat"),
        ]

        climbs = detect_climbs(segments)

        assert len(climbs) == 0

    def test_empty_segments(self):
        """Empty segment list should return empty climb list."""
        climbs = detect_climbs([])
        assert climbs == []

    def test_max_grade_tracking(self):
        """Max grade should be tracked across merged segments."""
        segments = [
            CourseSegment(0, 500, 500, 5.0, 25, 0, "climb"),
            CourseSegment(500, 1000, 500, 12.0, 60, 0, "steep_climb"),
            CourseSegment(1000, 1500, 500, 6.0, 30, 0, "climb"),
        ]

        climbs = detect_climbs(segments)

        assert len(climbs) == 1
        assert climbs[0].max_grade_pct == 12.0


class TestClimbCategorization:
    """Tests for climb category scoring."""

    def test_category_hc(self):
        """Score >= 80,000 should be HC."""
        # 10km at 8% = 80,000
        category = _categorize_climb(10000, 8.0)
        assert category == "HC"

    def test_category_1(self):
        """Score 64,000-80,000 should be Cat 1."""
        # 8km at 8% = 64,000
        category = _categorize_climb(8000, 8.0)
        assert category == "1"

    def test_category_2(self):
        """Score 32,000-64,000 should be Cat 2."""
        # 4km at 8% = 32,000
        category = _categorize_climb(4000, 8.0)
        assert category == "2"

    def test_category_3(self):
        """Score 16,000-32,000 should be Cat 3."""
        # 2km at 8% = 16,000
        category = _categorize_climb(2000, 8.0)
        assert category == "3"

    def test_category_4(self):
        """Score 8,000-16,000 should be Cat 4."""
        # 1km at 8% = 8,000
        category = _categorize_climb(1000, 8.0)
        assert category == "4"

    def test_category_none(self):
        """Score < 8,000 should be None (uncategorized)."""
        # 500m at 5% = 2,500
        category = _categorize_climb(500, 5.0)
        assert category is None

    def test_real_world_alpe_dhuez(self):
        """Alpe d'Huez: 13.8km at 8.1% = HC."""
        # 13800 * 8.1 / 100 = 111,780
        category = _categorize_climb(13800, 8.1)
        assert category == "HC"

    def test_real_world_box_hill(self):
        """Box Hill (UK): 2.5km at 5% = Cat 4."""
        # 2500 * 5 / 100 = 12,500
        category = _categorize_climb(2500, 5.0)
        assert category == "4"


class TestCourseSegmentDataclass:
    """Tests for CourseSegment dataclass."""

    def test_segment_creation(self):
        """Can create a CourseSegment."""
        segment = CourseSegment(
            start_distance_m=0,
            end_distance_m=1000,
            length_m=1000,
            avg_grade_pct=5.0,
            elevation_gain_m=50,
            elevation_loss_m=0,
            terrain_type="climb",
        )

        assert segment.start_distance_m == 0
        assert segment.end_distance_m == 1000
        assert segment.length_m == 1000
        assert segment.avg_grade_pct == 5.0
        assert segment.terrain_type == "climb"


class TestClimbDataclass:
    """Tests for Climb dataclass."""

    def test_climb_creation(self):
        """Can create a Climb."""
        climb = Climb(
            name="Col du Galibier",
            start_distance_m=5000,
            end_distance_m=22000,
            length_m=17000,
            avg_grade_pct=7.0,
            elevation_gain_m=1190,
            max_grade_pct=12.0,
            category="HC",
        )

        assert climb.name == "Col du Galibier"
        assert climb.length_m == 17000
        assert climb.category == "HC"

    def test_climb_without_name(self):
        """Climb can have None name."""
        climb = Climb(
            name=None,
            start_distance_m=0,
            end_distance_m=1000,
            length_m=1000,
            avg_grade_pct=5.0,
            elevation_gain_m=50,
            max_grade_pct=6.0,
            category="4",
        )

        assert climb.name is None



class TestAssignSegmentBearings:
    """Tests for assign_segment_bearings function."""

    def test_single_segment_northbound(self):
        """Single segment heading north should get bearing ~0."""
        segment = CourseSegment(
            start_distance_m=0,
            end_distance_m=1000,
            length_m=1000,
            avg_grade_pct=0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        )
        # Points going north: (0,0) -> (1,0) lat
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 1000.0)]

        assign_segment_bearings([segment], points)

        assert segment.bearing_deg is not None
        assert segment.bearing_deg == pytest.approx(0.0, abs=1.0)

    def test_single_segment_eastbound(self):
        """Single segment heading east should get bearing ~90."""
        segment = CourseSegment(
            start_distance_m=0,
            end_distance_m=1000,
            length_m=1000,
            avg_grade_pct=0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        )
        # Points going east: (0,0) -> (0,1) lon
        points = [(0.0, 0.0, 0.0), (0.0, 1.0, 1000.0)]

        assign_segment_bearings([segment], points)

        assert segment.bearing_deg is not None
        assert segment.bearing_deg == pytest.approx(90.0, abs=1.0)

    def test_multiple_segments(self):
        """Multiple segments should each get their own bearing."""
        seg1 = CourseSegment(
            start_distance_m=0,
            end_distance_m=500,
            length_m=500,
            avg_grade_pct=0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        )
        seg2 = CourseSegment(
            start_distance_m=500,
            end_distance_m=1000,
            length_m=500,
            avg_grade_pct=0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        )
        # First segment goes north, second goes east
        points = [
            (0.0, 0.0, 0.0),
            (0.5, 0.0, 250.0),
            (1.0, 0.0, 500.0),
            (1.0, 0.5, 750.0),
            (1.0, 1.0, 1000.0),
        ]

        assign_segment_bearings([seg1, seg2], points)

        assert seg1.bearing_deg is not None
        assert seg2.bearing_deg is not None
        assert seg1.bearing_deg == pytest.approx(0.0, abs=1.0)  # North
        assert seg2.bearing_deg == pytest.approx(90.0, abs=1.0)  # East

    def test_empty_segments(self):
        """Empty segments list should not raise."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 1000.0)]
        result = assign_segment_bearings([], points)
        assert result == []

    def test_empty_points(self):
        """Empty points list should not raise, bearings remain None."""
        segment = CourseSegment(
            start_distance_m=0,
            end_distance_m=1000,
            length_m=1000,
            avg_grade_pct=0,
            elevation_gain_m=0,
            elevation_loss_m=0,
            terrain_type="flat",
        )

        assign_segment_bearings([segment], [])

        assert segment.bearing_deg is None

    def test_real_world_course(self):
        """Test with realistic GPS coordinates from a cycling course."""
        # Simulating a course that goes roughly northeast then east
        seg1 = CourseSegment(
            start_distance_m=0,
            end_distance_m=2000,
            length_m=2000,
            avg_grade_pct=2.0,
            elevation_gain_m=40,
            elevation_loss_m=0,
            terrain_type="false_flat",
        )
        seg2 = CourseSegment(
            start_distance_m=2000,
            end_distance_m=4000,
            length_m=2000,
            avg_grade_pct=-1.0,
            elevation_gain_m=0,
            elevation_loss_m=20,
            terrain_type="false_flat",
        )
        # Zurich area coordinates going NE then E
        points = [
            (47.3769, 8.5417, 0.0),      # Start
            (47.3850, 8.5550, 1000.0),   # Midpoint seg1
            (47.3930, 8.5680, 2000.0),   # End seg1 / Start seg2
            (47.3935, 8.5900, 3000.0),   # Midpoint seg2
            (47.3940, 8.6120, 4000.0),   # End seg2
        ]

        assign_segment_bearings([seg1, seg2], points)

        # Segment 1 should be roughly NE (~40-50°)
        assert seg1.bearing_deg is not None
        assert 35 < seg1.bearing_deg < 55

        # Segment 2 should be roughly E (~85-95°)
        assert seg2.bearing_deg is not None
        assert 80 < seg2.bearing_deg < 100
