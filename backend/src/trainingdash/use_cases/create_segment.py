"""
CreateSegment use case — create a segment from activity record indices.

This use case handles manual segment creation from activity selections:
1. Validate activity ownership and index range
2. Compute geometry from activity records
3. Determine segment type (climb/sprint/custom) and category
4. Check for duplicate segments
5. Create segment with status='approved'
6. Trigger retroactive matching job
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from geoalchemy2 import WKTElement

from trainingdash.domain.climb_detection import categorize_climb
from trainingdash.domain.segment_geometry import (
    compute_segment_geometry,
    haversine_distance,
)
from trainingdash.domain.segment_matching import compute_path_overlap
from trainingdash.jobs import enqueue_retroactive_match_job
from trainingdash.repositories.postgres.models import Segment
from trainingdash.repositories.protocols import ActivityRepo, RecordRepo, SegmentRepo

logger = logging.getLogger(__name__)

# Validation constants
MIN_NAME_LENGTH = 3
MAX_NAME_LENGTH = 100
MIN_SEGMENT_POINTS = 2

# Type classification thresholds
CLIMB_MIN_GRADE_PCT = 3.0
CLIMB_MIN_LENGTH_M = 300.0
SPRINT_MIN_LENGTH_M = 150.0
SPRINT_MAX_LENGTH_M = 600.0
SPRINT_MAX_GRADE_PCT = 3.0
SPRINT_MIN_GRADE_PCT = -3.0

# Duplicate detection thresholds
DUPLICATE_POINT_TOLERANCE_M = 25.0
DUPLICATE_OVERLAP_PCT = 95.0


@dataclass
class CreateSegmentResult:
    """Result of segment creation attempt."""

    success: bool
    segment: Segment | None = None
    error: str | None = None
    duplicate_segment_id: UUID | None = None


class CreateSegment:
    """
    Use case for creating a segment from activity record indices.

    Creates a globally shared segment from a user's activity selection.
    Handles validation, geometry computation, type classification,
    duplicate detection, and triggering retroactive matching.
    """

    def __init__(
        self,
        activity_repo: ActivityRepo,
        record_repo: RecordRepo,
        segment_repo: SegmentRepo,
    ) -> None:
        """
        Initialize with repository dependencies.

        Args:
            activity_repo: Repository for activity access
            record_repo: Repository for activity records
            segment_repo: Repository for segment persistence
        """
        self._activity_repo = activity_repo
        self._record_repo = record_repo
        self._segment_repo = segment_repo

    async def execute(
        self,
        user_id: int,
        activity_id: UUID,
        start_index: int,
        end_index: int,
        name: str,
    ) -> CreateSegmentResult:
        """
        Create a segment from activity record indices.

        Steps:
        1. Validate activity ownership
        2. Validate name length
        3. Validate index range
        4. Load activity records
        5. Compute geometry (polyline, bounds, stats)
        6. Determine type and category from geometry
        7. Check for duplicates (25m start/end + 95% overlap)
        8. Create segment with status='approved'
        9. Enqueue retroactive_match_job

        Args:
            user_id: User creating the segment
            activity_id: Source activity UUID
            start_index: Start record index (inclusive)
            end_index: End record index (inclusive)
            name: Segment name

        Returns:
            CreateSegmentResult with success status and segment or error
        """
        # Validate name
        name = name.strip()
        if len(name) < MIN_NAME_LENGTH:
            return CreateSegmentResult(
                success=False,
                error=f"Name must be at least {MIN_NAME_LENGTH} characters",
            )
        if len(name) > MAX_NAME_LENGTH:
            return CreateSegmentResult(
                success=False,
                error=f"Name must be at most {MAX_NAME_LENGTH} characters",
            )

        # Validate activity ownership
        activity = await self._activity_repo.get_by_id(activity_id, user_id)
        if activity is None:
            return CreateSegmentResult(
                success=False,
                error="Activity not found or not owned by user",
            )

        # Validate index range
        if start_index < 0:
            return CreateSegmentResult(
                success=False,
                error="Start index must be non-negative",
            )
        if end_index <= start_index:
            return CreateSegmentResult(
                success=False,
                error="End index must be greater than start index",
            )

        # Load activity records
        records = await self._record_repo.list_for_activity(activity_id)
        if not records:
            return CreateSegmentResult(
                success=False,
                error="Activity has no records",
            )

        if end_index >= len(records):
            return CreateSegmentResult(
                success=False,
                error=f"End index {end_index} exceeds record count {len(records)}",
            )

        # Convert ORM records to dicts for domain functions
        record_dicts = [
            {
                "lat": r.lat,
                "lon": r.lon,
                "altitude_m": r.altitude_m,
                "distance_m": r.distance_m,
            }
            for r in records
        ]

        # Validate we have enough GPS points
        segment_records = record_dicts[start_index : end_index + 1]
        valid_gps_points = sum(
            1 for r in segment_records if r["lat"] is not None and r["lon"] is not None
        )
        if valid_gps_points < MIN_SEGMENT_POINTS:
            return CreateSegmentResult(
                success=False,
                error="Segment must contain at least 2 valid GPS points",
            )

        # Compute geometry
        try:
            geometry = compute_segment_geometry(record_dicts, start_index, end_index)
        except ValueError as e:
            return CreateSegmentResult(
                success=False,
                error=f"Failed to compute geometry: {e}",
            )

        # Determine segment type and category
        segment_type, climb_category = self._classify_segment(
            distance_m=geometry.distance_m,
            avg_grade_pct=geometry.avg_grade_pct,
        )

        # Check for duplicates
        duplicate = await self._find_duplicate(
            start_lat=geometry.start_lat,
            start_lon=geometry.start_lon,
            end_lat=geometry.end_lat,
            end_lon=geometry.end_lon,
            polyline=geometry.polyline,
        )
        if duplicate is not None:
            return CreateSegmentResult(
                success=False,
                error="A similar segment already exists",
                duplicate_segment_id=duplicate.id,
            )

        # Create PostGIS geometry objects
        start_point = WKTElement(
            f"POINT({geometry.start_lon} {geometry.start_lat})", srid=4326
        )
        end_point = WKTElement(
            f"POINT({geometry.end_lon} {geometry.end_lat})", srid=4326
        )
        min_lat, min_lon, max_lat, max_lon = geometry.bounds
        bounds_polygon = WKTElement(
            f"POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
            f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))",
            srid=4326,
        )

        # Create segment
        segment = Segment(
            name=name,
            type=segment_type,
            status="approved",
            climb_category=climb_category,
            polyline=geometry.polyline,
            start_point=start_point,
            end_point=end_point,
            bounds=bounds_polygon,
            direction_bearing=geometry.direction_bearing,
            distance_m=geometry.distance_m,
            elevation_gain_m=geometry.elevation_gain_m,
            avg_grade_pct=geometry.avg_grade_pct,
            max_grade_pct=geometry.max_grade_pct,
            gradient_segments=[
                {"distance_m": gs.distance_m, "grade_pct": gs.grade_pct}
                for gs in geometry.gradient_segments
            ],
            created_by=user_id,
            source_activity_id=activity_id,
        )

        saved_segment = await self._segment_repo.save(segment)

        # Enqueue retroactive matching job
        try:
            await enqueue_retroactive_match_job(str(saved_segment.id))
            logger.info(
                f"Enqueued retroactive match job for segment {saved_segment.id}"
            )
        except Exception as e:
            # Log but don't fail - segment was created successfully
            logger.warning(
                f"Failed to enqueue retroactive match job for segment {saved_segment.id}: {e}"
            )

        return CreateSegmentResult(success=True, segment=saved_segment)

    def _classify_segment(
        self,
        distance_m: float,
        avg_grade_pct: float,
    ) -> tuple[str, str | None]:
        """
        Classify segment type and category from geometry.

        Returns:
            Tuple of (type, climb_category).
            climb_category is None for non-climb segments.
        """
        # Check for climb: avg_grade >= 3% and length >= 300m
        if avg_grade_pct >= CLIMB_MIN_GRADE_PCT and distance_m >= CLIMB_MIN_LENGTH_M:
            category = categorize_climb(distance_m, avg_grade_pct)
            return ("climb", category)

        # Check for sprint: 150-600m and -3% <= grade <= 3%
        if (
            SPRINT_MIN_LENGTH_M <= distance_m <= SPRINT_MAX_LENGTH_M
            and SPRINT_MIN_GRADE_PCT <= avg_grade_pct <= SPRINT_MAX_GRADE_PCT
        ):
            return ("sprint", None)

        # Default to custom
        return ("custom", None)

    async def _find_duplicate(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        polyline: str,
    ) -> Segment | None:
        """
        Check for existing segment that is a duplicate.

        A segment is a duplicate if:
        - Start point within 25m
        - End point within 25m
        - 95% path overlap

        Returns:
            The duplicate Segment if found, None otherwise.
        """
        # Get all approved segments (could optimize with spatial query)
        candidates = await self._segment_repo.list_approved(limit=1000)

        for candidate in candidates:
            # Check start point distance
            # Extract lat/lon from PostGIS Point (WKBElement)
            # For fake repos, these might be simple tuples; for real repos, need extraction
            candidate_start_lat, candidate_start_lon = self._extract_point_coords(
                candidate.start_point
            )
            candidate_end_lat, candidate_end_lon = self._extract_point_coords(
                candidate.end_point
            )

            if candidate_start_lat is None or candidate_end_lat is None:
                continue

            start_dist = haversine_distance(
                start_lat, start_lon, candidate_start_lat, candidate_start_lon
            )
            if start_dist > DUPLICATE_POINT_TOLERANCE_M:
                continue

            # Check end point distance
            end_dist = haversine_distance(
                end_lat, end_lon, candidate_end_lat, candidate_end_lon
            )
            if end_dist > DUPLICATE_POINT_TOLERANCE_M:
                continue

            # Check path overlap
            # Create synthetic activity records from candidate polyline for overlap calc
            from trainingdash.domain.polyline import decode_polyline

            candidate_points = decode_polyline(candidate.polyline)
            if len(candidate_points) < 2:
                continue

            # Build fake records for the new segment
            new_points = decode_polyline(polyline)
            if len(new_points) < 2:
                continue

            fake_records = [{"lat": lat, "lon": lon} for lat, lon in new_points]

            overlap = compute_path_overlap(
                fake_records,
                0,
                len(fake_records) - 1,
                candidate.polyline,
                buffer_m=35,
            )

            if overlap >= DUPLICATE_OVERLAP_PCT:
                return candidate

        return None

    def _extract_point_coords(
        self, point: object
    ) -> tuple[float | None, float | None]:
        """
        Extract lat/lon from a PostGIS Point or simple tuple.

        Handles both real WKBElement from Postgres and simple tuples from fakes.
        """
        if point is None:
            return (None, None)

        # For fake repos using tuples
        if isinstance(point, tuple) and len(point) == 2:
            return point

        # For WKTElement used in tests
        if hasattr(point, "data"):
            # Parse "POINT(lon lat)" format
            data = str(point.data)
            if data.startswith("POINT("):
                coords = data[6:-1].split()
                if len(coords) == 2:
                    return (float(coords[1]), float(coords[0]))  # lat, lon

        # For real WKBElement from PostGIS
        try:
            from geoalchemy2.shape import to_shape

            shape = to_shape(point)
            return (shape.y, shape.x)  # lat, lon
        except Exception:
            pass

        return (None, None)
