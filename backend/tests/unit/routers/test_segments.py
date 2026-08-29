"""Tests for segments API router endpoints."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trainingdash.routers.segments import (
    CreateSegmentRequest,
    UpdateSegmentRequest,
    effort_summary,
    segment_summary,
)


class TestCreateSegmentRequest:
    """Tests for CreateSegmentRequest validation."""

    def test_valid_request(self):
        """Should accept valid request."""
        request = CreateSegmentRequest(
            name="Col du Galibier",
            activity_id=uuid4(),
            start_index=100,
            end_index=500,
        )
        assert request.name == "Col du Galibier"
        assert request.start_index == 100
        assert request.end_index == 500

    def test_name_too_short(self):
        """Should reject names shorter than 3 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSegmentRequest(
                name="AB",
                activity_id=uuid4(),
                start_index=0,
                end_index=10,
            )
        assert "String should have at least 3 characters" in str(exc_info.value)

    def test_name_too_long(self):
        """Should reject names longer than 100 characters."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSegmentRequest(
                name="A" * 101,
                activity_id=uuid4(),
                start_index=0,
                end_index=10,
            )
        assert "String should have at most 100 characters" in str(exc_info.value)

    def test_negative_start_index(self):
        """Should reject negative start_index."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSegmentRequest(
                name="Test Segment",
                activity_id=uuid4(),
                start_index=-1,
                end_index=10,
            )
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_negative_end_index(self):
        """Should reject negative end_index."""
        with pytest.raises(ValidationError) as exc_info:
            CreateSegmentRequest(
                name="Test Segment",
                activity_id=uuid4(),
                start_index=0,
                end_index=-1,
            )
        assert "greater than or equal to 0" in str(exc_info.value)


class TestUpdateSegmentRequest:
    """Tests for UpdateSegmentRequest validation."""

    def test_valid_request(self):
        """Should accept valid request."""
        request = UpdateSegmentRequest(name="New Segment Name")
        assert request.name == "New Segment Name"

    def test_name_too_short(self):
        """Should reject names shorter than 3 characters."""
        with pytest.raises(ValidationError):
            UpdateSegmentRequest(name="AB")

    def test_name_too_long(self):
        """Should reject names longer than 100 characters."""
        with pytest.raises(ValidationError):
            UpdateSegmentRequest(name="X" * 101)


class TestSegmentSummary:
    """Tests for segment_summary serializer."""

    def test_serializes_all_fields(self):
        """Should serialize all required fields."""
        from unittest.mock import MagicMock

        segment = MagicMock()
        segment.id = uuid4()
        segment.name = "Alpe d'Huez"
        segment.type = "climb"
        segment.climb_category = "hc"
        segment.distance_m = 13800.0
        segment.elevation_gain_m = 1071.0
        segment.avg_grade_pct = 8.1
        segment.effort_count = 1000
        segment.athlete_count = 500

        result = segment_summary(segment)

        assert result["id"] == str(segment.id)
        assert result["name"] == "Alpe d'Huez"
        assert result["type"] == "climb"
        assert result["climb_category"] == "hc"
        assert result["distance_m"] == 13800.0
        assert result["elevation_gain_m"] == 1071.0
        assert result["avg_grade_pct"] == 8.1
        assert result["effort_count"] == 1000
        assert result["athlete_count"] == 500

    def test_handles_null_category(self):
        """Should handle segments without climb category."""
        from unittest.mock import MagicMock

        segment = MagicMock()
        segment.id = uuid4()
        segment.name = "Sprint Segment"
        segment.type = "sprint"
        segment.climb_category = None
        segment.distance_m = 300.0
        segment.elevation_gain_m = 5.0
        segment.avg_grade_pct = 1.5
        segment.effort_count = 50
        segment.athlete_count = 20

        result = segment_summary(segment)

        assert result["climb_category"] is None
        assert result["type"] == "sprint"


class TestEffortSummary:
    """Tests for effort_summary serializer."""

    def test_serializes_all_fields(self):
        """Should serialize all effort fields."""
        from unittest.mock import MagicMock

        effort = MagicMock()
        effort.id = uuid4()
        effort.segment_id = uuid4()
        effort.activity_id = uuid4()
        effort.started_at = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
        effort.elapsed_time_seconds = 1800
        effort.moving_time_seconds = 1750
        effort.avg_power_watts = 280
        effort.avg_hr_bpm = 165
        effort.is_pr = True

        result = effort_summary(effort)

        assert result["id"] == str(effort.id)
        assert result["segment_id"] == str(effort.segment_id)
        assert result["activity_id"] == str(effort.activity_id)
        assert result["elapsed_time_seconds"] == 1800
        assert result["moving_time_seconds"] == 1750
        assert result["avg_power_watts"] == 280
        assert result["avg_hr_bpm"] == 165
        assert result["is_pr"] is True

    def test_handles_null_optional_fields(self):
        """Should handle efforts without power/HR data."""
        from unittest.mock import MagicMock

        effort = MagicMock()
        effort.id = uuid4()
        effort.segment_id = uuid4()
        effort.activity_id = uuid4()
        effort.started_at = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
        effort.elapsed_time_seconds = 300
        effort.moving_time_seconds = None
        effort.avg_power_watts = None
        effort.avg_hr_bpm = None
        effort.is_pr = False

        result = effort_summary(effort)

        assert result["moving_time_seconds"] is None
        assert result["avg_power_watts"] is None
        assert result["avg_hr_bpm"] is None
        assert result["is_pr"] is False


class TestBoundsQueryParsing:
    """Tests for bounds query parameter parsing."""

    def test_valid_bounds_format(self):
        """Should parse valid comma-separated bounds."""
        bounds = "46.0,6.0,47.0,7.0"
        parts = [float(x) for x in bounds.split(",")]
        assert len(parts) == 4
        assert parts == [46.0, 6.0, 47.0, 7.0]

    def test_invalid_bounds_format(self):
        """Should fail on invalid bounds format."""
        bounds = "invalid,bounds"
        with pytest.raises(ValueError):
            [float(x) for x in bounds.split(",")]

    def test_wrong_number_of_parts(self):
        """Should detect wrong number of bound components."""
        bounds = "46.0,6.0,47.0"  # Only 3 parts
        parts = [float(x) for x in bounds.split(",")]
        assert len(parts) != 4


class TestCategoryQueryParsing:
    """Tests for category query parameter parsing."""

    def test_single_category(self):
        """Should parse single category."""
        category = "hc"
        result = category.split(",")
        assert result == ["hc"]

    def test_multiple_categories(self):
        """Should parse comma-separated categories."""
        category = "hc,1,2"
        result = category.split(",")
        assert result == ["hc", "1", "2"]

    def test_all_valid_categories(self):
        """Should handle all valid climb categories."""
        valid_categories = ["hc", "1", "2", "3", "4", "nc"]
        category = ",".join(valid_categories)
        result = category.split(",")
        assert result == valid_categories
