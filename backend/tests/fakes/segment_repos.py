"""In-memory fake implementations of Segment repositories for testing."""

from datetime import datetime
from uuid import UUID

from trainingdash.repositories.postgres.models import (
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)


class FakeSegmentRepo:
    """
    In-memory fake implementation of SegmentRepo protocol.

    Stores segments in a dict keyed by segment_id.
    Spatial queries (bounds, direction) are simplified for testing.
    """

    def __init__(self) -> None:
        self._segments: dict[UUID, Segment] = {}

    # --- Protocol methods ---

    async def get_by_id(self, segment_id: UUID) -> Segment | None:
        segment = self._segments.get(segment_id)
        if segment and segment.deleted_at is None:
            return segment
        return None

    async def list_approved(
        self,
        type: str | None = None,
        category: list[str] | None = None,
        bounds: tuple[float, float, float, float] | None = None,
        search: str | None = None,
        sort: str = "popularity",
        order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[Segment]:
        segments = [
            s
            for s in self._segments.values()
            if s.status == "approved" and s.deleted_at is None
        ]

        # Apply filters
        if type:
            segments = [s for s in segments if s.type == type]

        if category:
            segments = [s for s in segments if s.climb_category in category]

        if search:
            search_lower = search.lower()
            segments = [s for s in segments if search_lower in s.name.lower()]

        # Note: bounds filter not implemented in fake (requires spatial data)
        # Tests needing bounds should use integration tests

        # Apply sorting
        sort_key = {
            "popularity": lambda s: s.effort_count,
            "name": lambda s: s.name.lower(),
            "distance": lambda s: s.distance_m,
            "elevation": lambda s: s.elevation_gain_m,
        }.get(sort, lambda s: s.effort_count)

        reverse = order == "desc"
        segments.sort(key=sort_key, reverse=reverse)

        # Apply pagination
        return segments[offset : offset + limit]

    async def count_approved(
        self,
        type: str | None = None,
        category: list[str] | None = None,
        bounds: tuple[float, float, float, float] | None = None,
        search: str | None = None,
    ) -> int:
        segments = [
            s
            for s in self._segments.values()
            if s.status == "approved" and s.deleted_at is None
        ]

        if type:
            segments = [s for s in segments if s.type == type]

        if category:
            segments = [s for s in segments if s.climb_category in category]

        if search:
            search_lower = search.lower()
            segments = [s for s in segments if search_lower in s.name.lower()]

        return len(segments)

    async def save(self, segment: Segment) -> Segment:
        if segment.created_at is None:
            segment.created_at = datetime.now()
        self._segments[segment.id] = segment
        return segment

    async def soft_delete(self, segment_id: UUID) -> bool:
        segment = self._segments.get(segment_id)
        if segment and segment.deleted_at is None:
            segment.deleted_at = datetime.now()
            return True
        return False

    async def find_candidates_for_matching(
        self,
        bounds: object,
        direction_bearing: float,
    ) -> list[Segment]:
        # Simplified: return all approved segments (real impl uses PostGIS)
        return [
            s
            for s in self._segments.values()
            if s.status == "approved" and s.deleted_at is None
        ]

    async def increment_counts(self, segment_id: UUID, new_athlete: bool) -> None:
        segment = self._segments.get(segment_id)
        if segment:
            segment.effort_count += 1
            if new_athlete:
                segment.athlete_count += 1

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored segments."""
        self._segments.clear()

    def all(self) -> list[Segment]:
        """Return all stored segments (for test assertions)."""
        return list(self._segments.values())

    def add(self, segment: Segment) -> Segment:
        """Synchronous helper to add a segment for test setup."""
        if segment.created_at is None:
            segment.created_at = datetime.now()
        self._segments[segment.id] = segment
        return segment


class FakeSegmentEffortRepo:
    """
    In-memory fake implementation of SegmentEffortRepo protocol.

    Stores efforts in a dict keyed by effort_id.
    """

    def __init__(self) -> None:
        self._efforts: dict[UUID, SegmentEffort] = {}

    # --- Protocol methods ---

    async def get_by_id(self, effort_id: UUID) -> SegmentEffort | None:
        return self._efforts.get(effort_id)

    async def list_for_segment(
        self,
        segment_id: UUID,
        user_id: int,
        sort: str = "time",
        order: str = "asc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[SegmentEffort]:
        efforts = [
            e
            for e in self._efforts.values()
            if e.segment_id == segment_id and e.user_id == user_id
        ]

        # Apply sorting
        sort_key = {
            "time": lambda e: e.elapsed_time_seconds,
            "date": lambda e: e.started_at,
            "power": lambda e: e.avg_power_watts or 0,
        }.get(sort, lambda e: e.elapsed_time_seconds)

        reverse = order == "desc"
        efforts.sort(key=sort_key, reverse=reverse)

        return efforts[offset : offset + limit]

    async def list_for_activity(self, activity_id: UUID) -> list[SegmentEffort]:
        efforts = [e for e in self._efforts.values() if e.activity_id == activity_id]
        efforts.sort(key=lambda e: e.start_index)
        return efforts

    async def save(self, effort: SegmentEffort) -> SegmentEffort:
        if effort.created_at is None:
            effort.created_at = datetime.now()
        self._efforts[effort.id] = effort
        return effort

    async def get_user_pr(self, segment_id: UUID, user_id: int) -> SegmentEffort | None:
        for effort in self._efforts.values():
            if (
                effort.segment_id == segment_id
                and effort.user_id == user_id
                and effort.is_pr
            ):
                return effort
        return None

    async def clear_user_pr(self, segment_id: UUID, user_id: int) -> None:
        for effort in self._efforts.values():
            if (
                effort.segment_id == segment_id
                and effort.user_id == user_id
                and effort.is_pr
            ):
                effort.is_pr = False

    async def count_for_segment(self, segment_id: UUID, user_id: int) -> int:
        return len(
            [
                e
                for e in self._efforts.values()
                if e.segment_id == segment_id and e.user_id == user_id
            ]
        )

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored efforts."""
        self._efforts.clear()

    def all(self) -> list[SegmentEffort]:
        """Return all stored efforts (for test assertions)."""
        return list(self._efforts.values())

    def add(self, effort: SegmentEffort) -> SegmentEffort:
        """Synchronous helper to add an effort for test setup."""
        if effort.created_at is None:
            effort.created_at = datetime.now()
        self._efforts[effort.id] = effort
        return effort


class FakeSegmentSuggestionRepo:
    """
    In-memory fake implementation of SegmentSuggestionRepo protocol.

    Stores suggestions in a dict keyed by suggestion_id.
    """

    def __init__(self) -> None:
        self._suggestions: dict[UUID, SegmentSuggestion] = {}

    # --- Protocol methods ---

    async def get_by_id(self, suggestion_id: UUID) -> SegmentSuggestion | None:
        return self._suggestions.get(suggestion_id)

    async def list_for_user(
        self,
        user_id: int,
        include_dismissed: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SegmentSuggestion]:
        suggestions = [s for s in self._suggestions.values() if s.user_id == user_id]

        if not include_dismissed:
            suggestions = [s for s in suggestions if s.dismissed_at is None]

        # Sort by repetition_count descending
        suggestions.sort(key=lambda s: s.repetition_count, reverse=True)

        return suggestions[offset : offset + limit]

    async def count_for_user(self, user_id: int, include_dismissed: bool = False) -> int:
        suggestions = [s for s in self._suggestions.values() if s.user_id == user_id]

        if not include_dismissed:
            suggestions = [s for s in suggestions if s.dismissed_at is None]

        return len(suggestions)

    async def save(self, suggestion: SegmentSuggestion) -> SegmentSuggestion:
        if suggestion.created_at is None:
            suggestion.created_at = datetime.now()
        self._suggestions[suggestion.id] = suggestion
        return suggestion

    async def dismiss(self, suggestion_id: UUID) -> bool:
        suggestion = self._suggestions.get(suggestion_id)
        if suggestion and suggestion.dismissed_at is None:
            suggestion.dismissed_at = datetime.now()
            return True
        return False

    async def dismiss_all(self, user_id: int) -> int:
        count = 0
        for suggestion in self._suggestions.values():
            if suggestion.user_id == user_id and suggestion.dismissed_at is None:
                suggestion.dismissed_at = datetime.now()
                count += 1
        return count

    async def get_for_user_segment(
        self, user_id: int, segment_id: UUID
    ) -> SegmentSuggestion | None:
        for suggestion in self._suggestions.values():
            if suggestion.user_id == user_id and suggestion.segment_id == segment_id:
                return suggestion
        return None

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored suggestions."""
        self._suggestions.clear()

    def all(self) -> list[SegmentSuggestion]:
        """Return all stored suggestions (for test assertions)."""
        return list(self._suggestions.values())

    def add(self, suggestion: SegmentSuggestion) -> SegmentSuggestion:
        """Synchronous helper to add a suggestion for test setup."""
        if suggestion.created_at is None:
            suggestion.created_at = datetime.now()
        self._suggestions[suggestion.id] = suggestion
        return suggestion
