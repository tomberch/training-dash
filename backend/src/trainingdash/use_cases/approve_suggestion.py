"""
Use case for approving a segment suggestion.

Converts a suggested segment to an approved one with a user-provided name.
Handles duplicate detection against existing approved segments.
"""

from dataclasses import dataclass
from uuid import UUID

from geoalchemy2 import WKTElement

from trainingdash.domain.climb_detection import categorize_climb
from trainingdash.domain.segment_geometry import (
    compute_segment_geometry,
    haversine_distance,
)
from trainingdash.domain.segment_matching import compute_path_overlap
from trainingdash.repositories.postgres.models import Segment
from trainingdash.repositories.protocols import (
    ActivityRepo,
    RecordRepo,
    SegmentRepo,
    SegmentSuggestionRepo,
)

# Type classification thresholds (shared with CreateSegment)
CLIMB_MIN_GRADE_PCT = 3.0
CLIMB_MIN_LENGTH_M = 300.0
SPRINT_MIN_LENGTH_M = 150.0
SPRINT_MAX_LENGTH_M = 600.0
SPRINT_MAX_GRADE_PCT = 3.0
SPRINT_MIN_GRADE_PCT = -3.0


def classify_segment(distance_m: float, avg_grade_pct: float) -> tuple[str, str | None]:
    """
    Classify a segment as climb / sprint / custom from its geometry.

    Shared by suggestion approval (endpoint overrides may change the
    shape, so the type must be re-derived) and manual creation.

    Returns (type, climb_category); climb_category is None for
    non-climb segments.
    """
    if avg_grade_pct >= CLIMB_MIN_GRADE_PCT and distance_m >= CLIMB_MIN_LENGTH_M:
        category = categorize_climb(distance_m, avg_grade_pct)
        return ("climb", category)
    if (
        SPRINT_MIN_LENGTH_M <= distance_m <= SPRINT_MAX_LENGTH_M
        and SPRINT_MIN_GRADE_PCT <= avg_grade_pct <= SPRINT_MAX_GRADE_PCT
    ):
        return ("sprint", None)
    return ("custom", None)


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
        record_repo: "RecordRepo | None" = None,
        activity_repo: "ActivityRepo | None" = None,
    ) -> None:
        """
        Args:
            segment_repo: Repository for segment operations
            suggestion_repo: Repository for suggestion operations
            record_repo: Repository for activity records. Required only
                when approving with endpoint overrides (the source
                activity's GPS track is re-sliced); None disables
                adjustments.
            activity_repo: Repository for activity ownership checks.
                Required alongside record_repo — the source activity must
                belong to the approving user before its records are read.
        """
        self._segment_repo = segment_repo
        self._suggestion_repo = suggestion_repo
        self._record_repo = record_repo
        self._activity_repo = activity_repo

    async def execute(
        self,
        user_id: int,
        suggestion_id: UUID,
        name: str,
        start_index: int | None = None,
        end_index: int | None = None,
    ) -> ApproveResult:
        """
        Approve a suggestion with the given name.

        Args:
            user_id: ID of the user approving the suggestion
            suggestion_id: UUID of the suggestion to approve
            name: Name to give the approved segment
            start_index: Optional start index on the source activity's GPS
                track — adjusts the segment's start point
            end_index: Optional end index — adjusts the segment's end point

        When either index is provided, the segment's geometry is recomputed
        from the source activity's records between the (possibly adjusted)
        indices, and the duplicate check runs against the NEW geometry —
        a 409 must still be possible for an adjusted shape.

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

        # Apply endpoint overrides: recompute geometry from the source
        # activity's GPS track before the duplicate check
        if start_index is not None or end_index is not None:
            adjusted = await self._apply_overrides(segment, user_id, start_index, end_index)
            if adjusted is not None:
                return adjusted

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

    async def _apply_overrides(
        self,
        segment: Segment,
        user_id: int,
        start_index: int | None,
        end_index: int | None,
    ) -> ApproveResult | None:
        """
        Rewrite the segment's geometry from the source activity's records.

        Both indices must be provided together (partial adjustment of one
        endpoint is ambiguous — the detected indices are not stored, so a
        lone index can't be paired with a default).

        Returns an ApproveResult on failure (caller returns it directly),
        or None on success (segment mutated in place).
        """
        if start_index is None or end_index is None:
            return ApproveResult(
                success=False,
                error="Both start and end index are required to adjust a suggestion",
            )
        if self._record_repo is None:
            return ApproveResult(
                success=False,
                error="Endpoint adjustment is not available for this suggestion",
            )
        if segment.source_activity_id is None:
            return ApproveResult(
                success=False,
                error="Suggestion has no source activity to adjust against",
            )
        if self._activity_repo is None:
            return ApproveResult(
                success=False,
                error="Endpoint adjustment is not available for this suggestion",
            )

        # Ownership: the source activity must belong to the approving user.
        # Suggested segments are global; without this check a second user
        # could read the original rider's GPS track via crafted indices.
        activity = await self._activity_repo.get_by_id(segment.source_activity_id, user_id)
        if activity is None:
            return ApproveResult(
                success=False,
                error="Source activity not found or not owned by user",
            )
        if start_index < 0 or end_index <= start_index:
            return ApproveResult(
                success=False,
                error="End index must be greater than start index",
            )

        records = await self._record_repo.list_for_activity(segment.source_activity_id)
        if not records:
            return ApproveResult(
                success=False,
                error="Source activity has no records",
            )
        if end_index >= len(records):
            return ApproveResult(
                success=False,
                error=f"End index {end_index} exceeds record count {len(records)}",
            )

        record_dicts = [
            {"lat": r.lat, "lon": r.lon, "altitude_m": r.altitude_m, "distance_m": r.distance_m}
            for r in records
        ]

        try:
            geometry = compute_segment_geometry(record_dicts, start_index, end_index)
        except ValueError as e:
            return ApproveResult(success=False, error=f"Failed to compute geometry: {e}")

        # Reclassify from the adjusted shape (reuse CreateSegment's rules)
        segment_type, climb_category = classify_segment(
            distance_m=geometry.distance_m,
            avg_grade_pct=geometry.avg_grade_pct,
        )

        # Rewrite geometry columns
        segment.start_point = WKTElement(f"POINT({geometry.start_lon} {geometry.start_lat})", srid=4326)
        segment.end_point = WKTElement(f"POINT({geometry.end_lon} {geometry.end_lat})", srid=4326)
        sw_lat, sw_lng, ne_lat, ne_lng = geometry.bounds
        segment.bounds = WKTElement(
            f"POLYGON(({sw_lng} {sw_lat}, {ne_lng} {sw_lat}, {ne_lng} {ne_lat}, "
            f"{sw_lng} {ne_lat}, {sw_lng} {sw_lat}))",
            srid=4326,
        )
        segment.polyline = geometry.polyline
        segment.direction_bearing = geometry.direction_bearing
        segment.distance_m = geometry.distance_m
        segment.elevation_gain_m = geometry.elevation_gain_m
        segment.avg_grade_pct = geometry.avg_grade_pct
        segment.max_grade_pct = geometry.max_grade_pct
        segment.elevation_profile = [
            {"distance_m": ep.distance_m, "elevation_m": ep.elevation_m, "grade_pct": ep.grade_pct}
            for ep in geometry.elevation_profile
        ]
        segment.type = segment_type
        segment.climb_category = climb_category

        return None

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
