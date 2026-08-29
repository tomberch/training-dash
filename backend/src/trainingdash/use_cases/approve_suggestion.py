"""
Use case for approving a segment suggestion.

Converts a suggested segment to an approved one with a user-provided name.
Handles duplicate detection against existing approved segments.
"""

from dataclasses import dataclass
from uuid import UUID

from trainingdash.domain.segment_geometry import haversine_distance
from trainingdash.domain.segment_matching import compute_path_overlap
from trainingdash.repositories.postgres.models import Segment
from trainingdash.repositories.protocols import SegmentRepo, SegmentSuggestionRepo


def _extract_point_coords(point) -> tuple[float, float]:
    """
    Extract lat/lon from a geometry point.

    Handles both:
    - GeoAlchemy2 WKBElement (requires to_shape)
    - Fake geometry objects with .x/.y attributes (for testing)

    Returns:
        Tuple of (latitude, longitude)
    """
    # Check if it's a fake geometry with direct x/y attributes
    if hasattr(point, "x") and hasattr(point, "y") and not hasattr(point, "data"):
        return (point.y, point.x)

    # Real PostGIS geometry - use to_shape
    from geoalchemy2.shape import to_shape

    shape = to_shape(point)
    return (shape.y, shape.x)


@dataclass
class ApproveResult:
    """Result of an approve suggestion operation."""

    success: bool
    segment: Segment | None = None
    error: str | None = None
    duplicate_segment: Segment | None = None  # Populated if 409 duplicate


class ApproveSuggestion:
    """
    Approve a segment suggestion, converting it to an approved segment.

    Workflow:
    1. Load suggestion, verify owned by user
    2. Load associated segment (status=suggested)
    3. Check for duplicate approved segments
    4. If duplicate: return error with existing segment
    5. Update segment: status=approved, name=name, created_by=user_id
    6. Delete the suggestion row
    7. Return approved segment (caller enqueues retroactive_match_job)
    """

    # Duplicate detection thresholds (from ticket #499 / #473)
    START_TOLERANCE_M = 25.0
    END_TOLERANCE_M = 25.0
    MIN_OVERLAP_PCT = 95.0

    def __init__(
        self,
        segment_repo: SegmentRepo,
        suggestion_repo: SegmentSuggestionRepo,
    ) -> None:
        self._segment_repo = segment_repo
        self._suggestion_repo = suggestion_repo

    async def execute(
        self,
        user_id: int,
        suggestion_id: UUID,
        name: str,
    ) -> ApproveResult:
        """
        Approve a suggestion with the given name.

        Args:
            user_id: ID of the user approving the suggestion
            suggestion_id: UUID of the suggestion to approve
            name: Name to give the approved segment

        Returns:
            ApproveResult with success status and either the approved segment
            or error details (including duplicate segment if applicable)
        """
        # Validate name
        name = name.strip()
        if len(name) < 3:
            return ApproveResult(
                success=False,
                error="Name must be at least 3 characters",
            )
        if len(name) > 100:
            return ApproveResult(
                success=False,
                error="Name must be at most 100 characters",
            )

        # Load suggestion
        suggestion = await self._suggestion_repo.get_by_id(suggestion_id)
        if suggestion is None:
            return ApproveResult(
                success=False,
                error="Suggestion not found",
            )

        # Verify ownership
        if suggestion.user_id != user_id:
            return ApproveResult(
                success=False,
                error="Suggestion belongs to a different user",
            )

        # Check if already dismissed
        if suggestion.dismissed_at is not None:
            return ApproveResult(
                success=False,
                error="Suggestion has already been dismissed",
            )

        # Load associated segment
        segment = await self._segment_repo.get_by_id(suggestion.segment_id)
        if segment is None:
            return ApproveResult(
                success=False,
                error="Associated segment not found",
            )

        # Verify segment is still in suggested state
        if segment.status != "suggested":
            return ApproveResult(
                success=False,
                error="Segment has already been approved",
            )

        # Check for duplicates among approved segments
        duplicate = await self._find_duplicate(segment)
        if duplicate is not None:
            return ApproveResult(
                success=False,
                error="A similar segment already exists",
                duplicate_segment=duplicate,
            )

        # Approve the segment
        segment.status = "approved"
        segment.name = name
        segment.created_by = user_id
        saved_segment = await self._segment_repo.save(segment)

        # Remove the suggestion (it's been acted upon)
        await self._suggestion_repo.dismiss(suggestion_id)

        return ApproveResult(
            success=True,
            segment=saved_segment,
        )

    async def _find_duplicate(self, segment: Segment) -> Segment | None:
        """
        Check if an approved segment duplicates the given segment.

        Duplicate criteria (from ticket #473):
        - Start point within 25m
        - End point within 25m
        - 95% path overlap

        Args:
            segment: The segment to check for duplicates

        Returns:
            The duplicate approved segment if found, None otherwise
        """
        # Get all approved segments (in production, this would use spatial queries)
        approved = await self._segment_repo.list_approved(limit=1000)

        # Extract segment start/end coordinates
        seg_start_lat, seg_start_lon = _extract_point_coords(segment.start_point)
        seg_end_lat, seg_end_lon = _extract_point_coords(segment.end_point)

        for candidate in approved:
            # Skip same segment (shouldn't happen, but be safe)
            if candidate.id == segment.id:
                continue

            # Extract candidate coordinates
            cand_start_lat, cand_start_lon = _extract_point_coords(candidate.start_point)
            cand_end_lat, cand_end_lon = _extract_point_coords(candidate.end_point)

            # Check start distance
            start_dist = haversine_distance(
                seg_start_lat,
                seg_start_lon,
                cand_start_lat,
                cand_start_lon,
            )
            if start_dist > self.START_TOLERANCE_M:
                continue

            # Check end distance
            end_dist = haversine_distance(
                seg_end_lat,
                seg_end_lon,
                cand_end_lat,
                cand_end_lon,
            )
            if end_dist > self.END_TOLERANCE_M:
                continue

            # Check path overlap
            # We need to convert segment polyline to fake "activity records" for overlap check
            from trainingdash.domain.polyline import decode_polyline

            segment_points = decode_polyline(segment.polyline)
            if not segment_points:
                continue

            # Build fake records from segment points
            fake_records = [{"lat": lat, "lon": lon} for lat, lon in segment_points]

            overlap = compute_path_overlap(
                activity_records=fake_records,
                start_index=0,
                end_index=len(fake_records) - 1,
                segment_polyline=candidate.polyline,
                buffer_m=35,  # Standard buffer for matching
            )

            if overlap >= self.MIN_OVERLAP_PCT:
                return candidate

        return None
