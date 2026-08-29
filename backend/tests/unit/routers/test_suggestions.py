"""Unit tests for suggestions router."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from trainingdash.routers.suggestions import (
    ApproveSuggestionRequest,
    segment_response,
    suggestion_response,
)


# =============================================================================
# Request Model Tests
# =============================================================================


class TestApproveSuggestionRequest:
    """Tests for ApproveSuggestionRequest validation."""

    def test_valid_request(self):
        """Valid request with proper name."""
        request = ApproveSuggestionRequest(name="Alpe d'Huez")
        assert request.name == "Alpe d'Huez"

    def test_name_too_short(self):
        """Name must be at least 3 characters."""
        with pytest.raises(ValidationError) as exc_info:
            ApproveSuggestionRequest(name="AB")
        assert "String should have at least 3 characters" in str(exc_info.value)

    def test_name_too_long(self):
        """Name must be at most 100 characters."""
        with pytest.raises(ValidationError) as exc_info:
            ApproveSuggestionRequest(name="X" * 101)
        assert "String should have at most 100 characters" in str(exc_info.value)

    def test_name_at_min_length(self):
        """Name at minimum length is valid."""
        request = ApproveSuggestionRequest(name="ABC")
        assert request.name == "ABC"

    def test_name_at_max_length(self):
        """Name at maximum length is valid."""
        request = ApproveSuggestionRequest(name="X" * 100)
        assert len(request.name) == 100


# =============================================================================
# Serializer Tests
# =============================================================================


class TestSuggestionResponse:
    """Tests for suggestion_response serializer."""

    def test_serializes_all_fields(self):
        """Serializes all suggestion and segment fields."""
        suggestion = MagicMock()
        suggestion.id = uuid4()
        suggestion.segment_id = uuid4()
        suggestion.repetition_count = 3
        suggestion.first_ridden_at = datetime(2024, 1, 1, 10, 0, 0)
        suggestion.last_ridden_at = datetime(2024, 3, 15, 14, 30, 0)
        suggestion.expires_at = datetime(2024, 6, 13, 14, 30, 0)

        segment = MagicMock()
        segment.type = "climb"
        segment.climb_category = "3"
        segment.distance_m = 5000.0
        segment.elevation_gain_m = 400.0
        segment.avg_grade_pct = 8.0
        segment.max_grade_pct = 12.5
        segment.polyline = "encoded_polyline"
        segment.gradient_segments = [{"distance_m": 500, "grade_pct": 8.0}]

        # Mock PostGIS geometry
        start_shape = MagicMock()
        start_shape.y = 47.0
        start_shape.x = 8.0
        end_shape = MagicMock()
        end_shape.y = 47.05
        end_shape.x = 8.01

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "trainingdash.routers.suggestions.to_shape",
                lambda geom: start_shape if geom == segment.start_point else end_shape,
            )

            result = suggestion_response(suggestion, segment)

        assert result["id"] == str(suggestion.id)
        assert result["segment_id"] == str(suggestion.segment_id)
        assert result["segment_type"] == "climb"
        assert result["climb_category"] == "3"
        assert result["distance_m"] == 5000.0
        assert result["elevation_gain_m"] == 400.0
        assert result["avg_grade_pct"] == 8.0
        assert result["max_grade_pct"] == 12.5
        assert result["repetition_count"] == 3
        assert result["polyline"] == "encoded_polyline"
        assert result["gradient_segments"] == [{"distance_m": 500, "grade_pct": 8.0}]
        assert result["start_point"] == {"lat": 47.0, "lng": 8.0}
        assert result["end_point"] == {"lat": 47.05, "lng": 8.01}

    def test_handles_null_category(self):
        """Handles suggestion without climb category."""
        suggestion = MagicMock()
        suggestion.id = uuid4()
        suggestion.segment_id = uuid4()
        suggestion.repetition_count = 1
        suggestion.first_ridden_at = datetime.now()
        suggestion.last_ridden_at = datetime.now()
        suggestion.expires_at = datetime.now() + timedelta(days=90)

        segment = MagicMock()
        segment.type = "sprint"
        segment.climb_category = None
        segment.distance_m = 300.0
        segment.elevation_gain_m = 5.0
        segment.avg_grade_pct = 1.5
        segment.max_grade_pct = 2.0
        segment.polyline = "sprint_polyline"
        segment.gradient_segments = []

        start_shape = MagicMock()
        start_shape.y = 47.0
        start_shape.x = 8.0
        end_shape = MagicMock()
        end_shape.y = 47.003
        end_shape.x = 8.0

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "trainingdash.routers.suggestions.to_shape",
                lambda geom: start_shape if geom == segment.start_point else end_shape,
            )

            result = suggestion_response(suggestion, segment)

        assert result["segment_type"] == "sprint"
        assert result["climb_category"] is None


class TestSegmentResponse:
    """Tests for segment_response serializer."""

    def test_serializes_all_fields(self):
        """Serializes all segment fields."""
        segment = MagicMock()
        segment.id = uuid4()
        segment.name = "Test Climb"
        segment.type = "climb"
        segment.status = "approved"
        segment.climb_category = "4"
        segment.polyline = "encoded_polyline"
        segment.distance_m = 1000.0
        segment.elevation_gain_m = 100.0
        segment.avg_grade_pct = 10.0
        segment.max_grade_pct = 15.0
        segment.gradient_segments = [{"distance_m": 500, "grade_pct": 10.0}]
        segment.effort_count = 50
        segment.athlete_count = 10
        segment.created_by = 1
        segment.created_at = datetime(2024, 1, 15, 10, 0, 0)

        start_shape = MagicMock()
        start_shape.y = 47.0
        start_shape.x = 8.0
        end_shape = MagicMock()
        end_shape.y = 47.01
        end_shape.x = 8.0

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "trainingdash.routers.suggestions.to_shape",
                lambda geom: start_shape if geom == segment.start_point else end_shape,
            )

            result = segment_response(segment)

        assert result["id"] == str(segment.id)
        assert result["name"] == "Test Climb"
        assert result["type"] == "climb"
        assert result["status"] == "approved"
        assert result["climb_category"] == "4"
        assert result["polyline"] == "encoded_polyline"
        assert result["distance_m"] == 1000.0
        assert result["elevation_gain_m"] == 100.0
        assert result["avg_grade_pct"] == 10.0
        assert result["max_grade_pct"] == 15.0
        assert result["gradient_segments"] == [{"distance_m": 500, "grade_pct": 10.0}]
        assert result["effort_count"] == 50
        assert result["athlete_count"] == 10
        assert result["created_by"] == 1
        assert result["start_point"] == {"lat": 47.0, "lng": 8.0}
        assert result["end_point"] == {"lat": 47.01, "lng": 8.0}


# =============================================================================
# Router Endpoint Tests (using fake repos)
# =============================================================================


class TestListSuggestionsEndpoint:
    """Tests for list_suggestions endpoint logic."""

    @pytest.mark.asyncio
    async def test_empty_list(self):
        """Returns empty list when no suggestions."""
        from trainingdash.routers.suggestions import list_suggestions
        from tests.fakes.segment_repos import (
            FakeSegmentRepo,
            FakeSegmentSuggestionRepo,
        )

        user = MagicMock()
        user.id = 1

        suggestion_repo = FakeSegmentSuggestionRepo()
        segment_repo = FakeSegmentRepo()

        result = await list_suggestions(
            user=user,
            suggestion_repo=suggestion_repo,
            segment_repo=segment_repo,
            page=1,
            per_page=20,
        )

        assert result["items"] == []
        assert result["meta"]["total"] == 0
        assert result["meta"]["page"] == 1
        assert result["meta"]["total_pages"] == 1


class TestDismissSuggestionEndpoint:
    """Tests for dismiss_suggestion endpoint logic."""

    @pytest.mark.asyncio
    async def test_suggestion_not_found(self):
        """Returns 404 when suggestion doesn't exist."""
        from fastapi import HTTPException

        from trainingdash.routers.suggestions import dismiss_suggestion
        from tests.fakes.segment_repos import FakeSegmentSuggestionRepo

        user = MagicMock()
        user.id = 1

        suggestion_repo = FakeSegmentSuggestionRepo()

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_suggestion(
                user=user,
                suggestion_repo=suggestion_repo,
                suggestion_id=uuid4(),
            )

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_suggestion_belongs_to_different_user(self):
        """Returns 403 when suggestion belongs to different user."""
        from fastapi import HTTPException

        from trainingdash.repositories.postgres.models import SegmentSuggestion
        from trainingdash.routers.suggestions import dismiss_suggestion
        from tests.fakes.segment_repos import FakeSegmentSuggestionRepo

        user = MagicMock()
        user.id = 1

        suggestion_repo = FakeSegmentSuggestionRepo()

        # Add suggestion owned by different user
        suggestion = SegmentSuggestion(
            id=uuid4(),
            segment_id=uuid4(),
            user_id=2,  # Different user
            repetition_count=1,
            first_ridden_at=datetime.now(),
            last_ridden_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=90),
        )
        suggestion_repo.add(suggestion)

        with pytest.raises(HTTPException) as exc_info:
            await dismiss_suggestion(
                user=user,
                suggestion_repo=suggestion_repo,
                suggestion_id=suggestion.id,
            )

        assert exc_info.value.status_code == 403
        assert "different user" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_dismiss_success(self):
        """Successfully dismisses a suggestion."""
        from trainingdash.repositories.postgres.models import SegmentSuggestion
        from trainingdash.routers.suggestions import dismiss_suggestion
        from tests.fakes.segment_repos import FakeSegmentSuggestionRepo

        user = MagicMock()
        user.id = 1

        suggestion_repo = FakeSegmentSuggestionRepo()

        suggestion = SegmentSuggestion(
            id=uuid4(),
            segment_id=uuid4(),
            user_id=1,
            repetition_count=1,
            first_ridden_at=datetime.now(),
            last_ridden_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=90),
        )
        suggestion_repo.add(suggestion)

        # Should not raise
        result = await dismiss_suggestion(
            user=user,
            suggestion_repo=suggestion_repo,
            suggestion_id=suggestion.id,
        )

        # Result is None (204 No Content)
        assert result is None

        # Verify it was dismissed
        updated = await suggestion_repo.get_by_id(suggestion.id)
        assert updated.dismissed_at is not None


class TestDismissAllEndpoint:
    """Tests for dismiss_all_suggestions endpoint logic."""

    @pytest.mark.asyncio
    async def test_dismiss_all_success(self):
        """Successfully dismisses all suggestions."""
        from trainingdash.repositories.postgres.models import SegmentSuggestion
        from trainingdash.routers.suggestions import dismiss_all_suggestions
        from tests.fakes.segment_repos import FakeSegmentSuggestionRepo

        user = MagicMock()
        user.id = 1

        suggestion_repo = FakeSegmentSuggestionRepo()

        # Add multiple suggestions
        for _ in range(3):
            suggestion = SegmentSuggestion(
                id=uuid4(),
                segment_id=uuid4(),
                user_id=1,
                repetition_count=1,
                first_ridden_at=datetime.now(),
                last_ridden_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=90),
            )
            suggestion_repo.add(suggestion)

        # Should not raise
        result = await dismiss_all_suggestions(
            user=user,
            suggestion_repo=suggestion_repo,
        )

        # Result is None (204 No Content)
        assert result is None

        # Verify all were dismissed
        remaining = await suggestion_repo.list_for_user(user.id, include_dismissed=False)
        assert len(remaining) == 0
